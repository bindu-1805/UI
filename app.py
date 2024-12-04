from flask import Flask, render_template, send_file
import pandas as pd
import matplotlib.pyplot as plt
import io

app = Flask(__name__)

# Mock function to simulate real-time sensor data (replace with actual data-fetching logic)
def get_sensor_data():
    # Example: Read data from a CSV file
    data = pd.read_csv('weather_data.csv')
    latest_data = data.iloc[-1].to_dict()
    return latest_data, data

@app.route('/')
def index():
    # Get real-time sensor data and historical data
    latest_data, historical_data = get_sensor_data()

    # Render the index page, passing the latest weather data
    return render_template('index.html', latest_data=latest_data)

@app.route('/plot')
def plot_data():
    # Fetch historical weather data
    _, historical_data = get_sensor_data()

    # Convert columns to numeric and handle missing data
    columns_to_plot = ['Temperature', 'Humidity', 'Pressure']  # Add relevant columns here
    for col in columns_to_plot:
        historical_data[col] = pd.to_numeric(historical_data[col], errors='coerce')
    historical_data.dropna(subset=columns_to_plot, inplace=True)

    # Create subplots
    fig, axes = plt.subplots(1, 2, figsize=(15,6))  # Adjust grid size based on the number of plots
    fig.suptitle('Weather Data Trends', fontsize=16)

    # Plot Temperature vs Humidity
    axes[0].plot(historical_data['Temperature'], historical_data['Humidity'])
    axes[0].set_title('Temperature vs Humidity')
    axes[0].set_xlabel('Temperature (°C)')
    axes[0].set_ylabel('Humidity (%)')

    # Plot Temperature vs Pressure
    axes[1].plot(historical_data['Temperature'], historical_data['Pressure'])
    axes[1].set_title('Temperature vs Pressure')
    axes[1].set_xlabel('Temperature (°C)')
    axes[1].set_ylabel('Pressure (hPa)')

     # Adjust layout
    plt.tight_layout()

    # Save the plot to an in-memory file and send it as a response
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    return send_file(img, mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True)