from flask import Flask, render_template, send_file
import pandas as pd
import matplotlib.pyplot as plt
import io

app = Flask(__name__)

# Read sensor data 
def get_sensor_data():
    data = pd.read_csv('weather_data.csv')
    latest_data = data.iloc[-1].to_dict()
    return latest_data, data

# Function to read another CSV file
def get_pm_data():
    pm_data = pd.read_csv('sensor_readings.csv', header=None)  
    pm_data.columns = ['Timestamp', 'PM10_label', 'PM10_value', 'PM2.5_label', 'PM2.5_value']
    latest_pm_data = pm_data.iloc[-1]
    
    latest_pm_data_dict = {
        'PM10': latest_pm_data['PM10_value'],
        'PM2.5': latest_pm_data['PM2.5_value']
    }

    return latest_pm_data_dict, pm_data

@app.route('/')
def index():
    # Get real-time sensor data and historical data
    latest_data, _ = get_sensor_data()
    latest_pm_data, _ = get_pm_data()  # Get the last row

    # Render the index page, passing the latest weather data
    return render_template('index.html', latest_data=latest_data, latest_pm_data=latest_pm_data)

@app.route('/plot')
def plot_data():
    # Fetch historical weather data
    _, historical_data = get_sensor_data()

    # Convert columns to numeric and handle missing data
    columns_to_plot = ['Temperature', 'Humidity', 'Pressure', 'Rainfall', 'Windspeed']  # Add relevant columns here
    for col in columns_to_plot:
        historical_data[col] = pd.to_numeric(historical_data[col], errors='coerce')
    historical_data['Timestamp'] = pd.to_datetime(historical_data['Timestamp'])
    historical_data.dropna(subset=columns_to_plot, inplace=True)

    # Create subplots
    fig, axes = plt.subplots(3,2, figsize=(24,24)) 
    fig.delaxes(axes[2, 1]) 
    fig.suptitle('Weather Data Trends', fontsize=40)

    # Common plot settings
    plot_settings = {
        'fontsize': 16,
        'linewidth': 2
    }

    # Plot Temperature 
    axes[0,0].plot(historical_data['Temperature'], historical_data['Timestamp'], color='red', linewidth=plot_settings['linewidth'])
    axes[0,0].set_title('Temperature over Time', fontsize=20)
    axes[0,0].set_xlabel('Temperature (°C)', fontsize=plot_settings['fontsize'])
    axes[0,0].set_ylabel('Timestamp', fontsize=plot_settings['fontsize'])

    # Plot Humidity
    axes[0,1].plot(historical_data['Humidity'], historical_data['Timestamp'], color='green', linewidth=plot_settings['linewidth'])
    axes[0,1].set_title('Humidity over Time', fontsize=20)
    axes[0,1].set_xlabel('Humidity (%)', fontsize=plot_settings['fontsize'])
    axes[0,1].set_ylabel('Timestamp', fontsize=plot_settings['fontsize'])

    # Plot Pressure
    axes[1,0].plot(historical_data['Pressure'], historical_data['Timestamp'], color='blue', linewidth=plot_settings['linewidth'])
    axes[1,0].set_title('Pressure over Time', fontsize=20)
    axes[1,0].set_xlabel('Pressure (hPa)', fontsize=plot_settings['fontsize'])
    axes[1,0].set_ylabel('Timestamp', fontsize=plot_settings['fontsize'])

     # Plot Rainfall
    axes[1, 1].plot(historical_data['Rainfall'], historical_data['Timestamp'], color='purple', linewidth=plot_settings['linewidth'])
    axes[1, 1].set_title('Rainfall over Time', fontsize=20)
    axes[1, 1].set_xlabel('Rainfall (ml)', fontsize=plot_settings['fontsize'])
    axes[1, 1].set_ylabel('Timestamp', fontsize=plot_settings['fontsize'])

     # Plot Wind speed
    axes[2, 0].plot(historical_data['Windspeed'], historical_data['Timestamp'], color='orange', linewidth=plot_settings['linewidth'])
    axes[2, 0].set_title('Wind speed over Time', fontsize=20)
    axes[2, 0].set_xlabel('Windspeed (km/hr)', fontsize=plot_settings['fontsize'])
    axes[2, 0].set_ylabel('Timestamp', fontsize=plot_settings['fontsize'])
    
     # Adjust layout
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.subplots_adjust(hspace=0.4)

    # Save the plot to an in-memory file and send it as a response
    img = io.BytesIO()
    plt.savefig(img, format='png', dpi=100)
    img.seek(0)
    return send_file(img, mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True)
