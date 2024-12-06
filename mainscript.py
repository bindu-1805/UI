import threading
import time
import csv
import os
import RPi.GPIO as GPIO
from datetime import datetime, timedelta
import smbus2
import bme280
from serial import Serial, SerialException
import logging

# Air Quality (Nova SDS018) Setup
DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"  # Serial port to use if no other specified
DEFAULT_BAUD_RATE = 9600  # Serial baud rate to use if no other specified
DEFAULT_SERIAL_TIMEOUT = 2  # Serial timeout to use if not specified
DEFAULT_READ_TIMEOUT = 1  # How long to sit looking for the correct character sequence.
DEFAULT_LOGGING_LEVEL = logging.DEBUG  # Set to DEBUG for detailed logs

MSG_CHAR_1 = b'\xAA'  # First character to be received in a valid packet
MSG_CHAR_2 = b'\xC0'

# CSV File Setup
csv_file = "weather_data.csv"
if not os.path.exists(csv_file):
    with open(csv_file,"w",newline="") as file:
        writer=csv.writer(file)
        writer.writerow([ "Timestamp", "Windspeed", "Rainfall", "Winddirection", "Temperature", "Pressure", "Humidity"])
        
# Cleanup any previous configurations
GPIO.cleanup()

# GPIO Setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

#Anemometer Variables
HALL_SENSOR_PIN = 13
RADIUS_CM = 2.0
CIRCUMFERENCE_CM = 2 * 3.14159 * RADIUS_CM
lastState = GPIO.HIGH
pulseCount = 0

# Rain Gauge Variables
RAIN_SENSOR_PIN = 5
rainfall_ml = 0
rain_per_tip = 2.5

# Wind Vane Variables
WIND_VANE_PINS = [27, 23, 17, 22]
DIRECTION_MAPPING = {
    (0, 0, 0, 0): "Invalid",
    (0, 1, 1, 1): "North",
    (1, 0, 1, 1): "East",
    (1, 1, 0, 1): "South",
    (1, 1, 1, 0): "West",
    (0, 0, 1, 0): "North East",
    (1, 0, 0, 1): "South East",
    (1, 1, 0, 0): "South West",
    (0, 1, 1, 0): "North West"
}

# BME280 Setup
I2C_PORT = 1
BME280_ADDRESS = 0x76
bus = smbus2.SMBus(I2C_PORT)
calibration_params = bme280.load_calibration_params(bus, BME280_ADDRESS)

# Function Definitions
def read_anemometer():
    global pulseCount
    GPIO.setup(HALL_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def pulse_detected(channel):
        global pulseCount
        pulseCount += 1
        print(f"Pulse count: {pulseCount}")
    
    GPIO.add_event_detect(HALL_SENSOR_PIN, GPIO.FALLING, callback=pulse_detected, bouncetime=10)   

    while True:
        pulseCount=0
        startTime = time.time()
        endTime = startTime + 10  # Count for 10 seconds
        #print("Starting pulse count...")
        while time.time() < endTime:
            time.sleep(0.1)  # Avoid busy-waiting
        rpm = (pulseCount / 10) * 60
        print(f"rpm: {rpm}")
        windspeed = (rpm*0.03)*6.0
        print(f"Wind Speed (m/s): {windspeed}")
        time.sleep(1)
        
def read_rain_gauge():
    global rainfall_ml
    GPIO.setup(RAIN_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    def sensor_callback(channel):
        global rainfall_ml
        rainfall_ml += rain_per_tip

    GPIO.add_event_detect(RAIN_SENSOR_PIN, GPIO.BOTH,callback=sensor_callback, bouncetime=300)
    
    while True:
        time.sleep(1)

def read_wind_vane():
    global wind_direction
    for pin in WIND_VANE_PINS:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    while True:
        sensor_states = tuple(GPIO.input(pin) for pin in WIND_VANE_PINS)
        wind_direction = DIRECTION_MAPPING.get(sensor_states, "Unknown")
        time.sleep(10)
        
def read_bme280():
    global temperature, pressure, humidity
    while True:
        data = bme280.sample(bus, BME280_ADDRESS, calibration_params)
        temperature, pressure, humidity = data.temperature, data.pressure, data.humidity
        time.sleep(10)

class NovafitnessReading(object):
    """
    Describes a single reading from the Novafitness SDS018 sensor
    """
    def _init_(self, line):
        """
        Takes a line from the Novafitness serial port and converts it into
        an object containing the data
        """
        self.timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") 
        self.pm10 = round(((line[5] << 8) + line[4]) / 10, 1)  # PM10 reading
        self.pm25 = round(((line[3] << 8) + line[2]) / 10, 1)  # PM2.5 reading
        
    def _str_(self):
        return f"{self.timestamp},{self.pm10},{self.pm25}"
    
class NovafitnessException(Exception):
    """
    Exception to be thrown if any problems occur
    """
    pass

class Novafitness(object):
    """
    Actual interface to the Novafitness sensor
    """
    def _init_(self, port=DEFAULT_SERIAL_PORT, baud=DEFAULT_BAUD_RATE,
                 serial_timeout=DEFAULT_SERIAL_TIMEOUT, read_timeout=DEFAULT_READ_TIMEOUT,
                 log_level=DEFAULT_LOGGING_LEVEL):
        """
        Setup the interface for the sensor
        """
        self.logger = logging.getLogger("SDS018 Interface")
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(lineno)d - %(levelname)s - %(message)s')
        self.logger.setLevel(log_level)
        self.port = port
        self.logger.info("Serial port: %s", self.port)
        self.baud = baud
        self.logger.info("Baud rate: %s", self.baud)
        self.serial_timeout = serial_timeout
        self.logger.info("Serial Timeout: %s", self.serial_timeout)
        self.read_timeout = read_timeout
        self.logger.info("Read Timeout: %s", self.read_timeout)
        try:
            self.serial = Serial(
                port=self.port, baudrate=self.baud,
                timeout=self.serial_timeout)
            self.logger.debug("Port Opened Successfully")
        except SerialException as exp:
            self.logger.error(str(exp))
            raise NovafitnessException(str(exp))
        
    def set_log_level(self, log_level):
        """
        Enables the class logging level to be changed after it's created
        """
        self.logger.setLevel(log_level)
        
    def _verify(self, recv):
        """
        Uses the last 2 bytes of the data packet from the Novafitness sensor
        to verify that the data received is correct
        """
        calc = (recv[2] + recv[3] + recv[4] + recv[5] + recv[6] + recv[7]) % 256
        self.logger.debug(calc)
        sent = recv[-2]  # Combine the 2 bytes together
        if sent != calc:
            self.logger.error("Checksum failure %d != %d", sent, calc)
            self.logger.error(recv)
            raise NovafitnessException("Checksum failure")
        
    def read(self, perform_flush=True):
        """
        Reads a line from the serial port and returns it as a NovafitnessReading object.
        """
        recv = b''  # Empty byte string to hold the data
        start = datetime.utcnow()  # Start timer
        if perform_flush:
            self.serial.flush()  # Flush any data in the buffer
        while(datetime.utcnow() < (start + timedelta(seconds=self.read_timeout))):
            inp = self.serial.read()  # Read a character from the input
            if inp == MSG_CHAR_1:  # Check if it matches
                recv += inp  # If it does, add it to received string
                inp = self.serial.read()  # Read the next character
                if inp == MSG_CHAR_2:  # Check it's what's expected
                    recv += inp  # Add it to the received string
                    recv += self.serial.read(8)  # Read the remaining 8 bytes
                    self._verify(recv)  # Verify the checksum
                    return NovafitnessReading(recv)  # Return the reading object
            # If the character isn't what we are expecting, loop until timeout
        raise NovafitnessException("No message received")
    
def save_to_csv(reading):
    if reading.pm10 > 0 and reading.pm25 > 0:  # Only save if valid readings
        with open("sensor_readings.csv", mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([reading.timestamp, "PM10", reading.pm10, "PM2.5", reading.pm25])
            #print(f"Data saved")
    else:
        print("Invalid reading. Skipping save.")
        
def read_air_quality(port=DEFAULT_SERIAL_PORT, baud=DEFAULT_BAUD_RATE,
                     serial_timeout=DEFAULT_SERIAL_TIMEOUT, read_timeout=DEFAULT_READ_TIMEOUT):
    novafitness = Novafitness(port=port, baud=baud, serial_timeout=serial_timeout, 
                              read_timeout=read_timeout, log_level=logging.DEBUG)
    try:
        while True:
            # Read the sensor data
            reading = novafitness.read()
            #print(f"PM10: {reading.pm10}, PM2.5: {reading.pm25}, Timestamp: {reading.timestamp}")
            save_to_csv(reading)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
        
    except NovafitnessException as e:
        print(f"Error: {e}")
    finally:
        novafitness.serial.close()
        
def log_data():
    while True:
        with open(csv_file, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([
                datetime.now(),
                windspeed,
                rainfall_ml,
                wind_direction,
                temperature,
                pressure,
                humidity,
                
            ])
        time.sleep(1)
        
# Main Execution
if __name__ == "__main__":
    windspeed = 0
    rainfall_ml = 0
    wind_direction = "N/A"
    temperature, pressure, humidity = 0, 0, 0

    threads = [
        threading.Thread(target=read_anemometer),
        threading.Thread(target=read_rain_gauge),
        threading.Thread(target=read_wind_vane),
        threading.Thread(target=read_bme280),
        threading.Thread(target=read_air_quality),
        threading.Thread(target=log_data),
    ]

    for t in threads:
        t.start()

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("Exiting program.")
        GPIO.cleanup()
