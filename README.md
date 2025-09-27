# 🚚 Multimodal Tire Pickup Route Optimizer

A powerful Streamlit application that optimizes tire pickup routes using multiple vehicles with capacity constraints and working hours. Built with Google Maps API and OR-Tools for real-world route optimization.

## ✨ Features

- **🚛 Smart Multi-vehicle Optimization** - Intelligent redistribution between 1-3 vehicles
- **⏰ Strict Time Constraints** - Each vehicle respects individual working hours (600 min default)
- **🔄 Intelligent Redistribution** - Automatically redistributes tasks when vehicles exceed time limits
- **📦 Capacity Constraints** - Configurable tire capacity per vehicle (default: 300 tires)
- **🗺️ Real Routes** - Google Maps API integration for accurate distances and directions
- **🧪 Parallel Testing** - Async testing of 1, 2, 3 vehicle configurations simultaneously
- **🎲 Mock Data Generator** - Built-in test data with 44 Houston area addresses
- **📊 Interactive Maps** - Visual route display with Folium and detailed route visualization
- **⚡ OR-Tools Optimization** - Advanced constraint solver with time and capacity dimensions
- **🎯 Decision Analysis** - Detailed explanation of why specific vehicle counts were chosen

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Google Maps API key
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd RoadOpti
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your Google Maps API key
   ```

5. **Run the application**
   ```bash
   streamlit run app.py
   ```

6. **Open in browser**
   Navigate to `http://localhost:8501`

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_google_maps_api_key_here
```

### Application Settings

- **Max Vehicles**: 1-3 vehicles available
- **Max Tires per Vehicle**: 50-500 tires (default: 300)
- **Base Loading Time**: 0-60 minutes per stop (default: 1 min)
- **Loading Time per Tire**: 0.0-2.0 minutes (default: 0.1 min)
- **Working Hours**: Configurable start/end times (default: 7 AM - 5 PM)

## 📖 Usage

### Basic Workflow

1. **Configure constraints** - Set vehicle capacity, loading times, and working hours
2. **Add pickup stops** - Enter addresses and tire quantities for each stop
3. **Generate test data** - Use "🎲 Generate Mock Data" for quick testing
4. **Optimize routes** - Click "🚀 Optimize Routes" for standard optimization
5. **Test async** - Click "🧪 Test Async" to compare 1, 2, 3 vehicles in parallel
6. **View results** - See optimized routes, vehicle assignments, and interactive map

### Mock Data

The application includes 44 Houston-area addresses in `addresses.json` for testing:
- Click "🎲 Generate Mock Data" to auto-fill stops
- Random tire quantities (15-20 tires per stop)
- Perfect for testing different scenarios

### Optimization Modes

#### Standard Optimization
- Tests vehicles sequentially (1, then 2, then 3)
- Uses Google Maps for accurate distances and real routes
- Detailed route visualization with interactive maps
- Comprehensive decision analysis and explanations

#### Async Testing
- Tests all vehicle configurations in parallel (1, 2, 3 vehicles simultaneously)
- Faster execution with optimized distance calculations
- Quick comparison of different solutions
- Individual vehicle time analysis and constraint validation

## 🏗️ Architecture

### Core Components

- **`app.py`** - Main Streamlit application
- **`addresses.json`** - Mock data for testing
- **`.env`** - Environment variables (not tracked in git)

### Key Dependencies

- **Streamlit** - Web application framework
- **Google Maps API** - Geocoding and distance calculations
- **OR-Tools** - Vehicle routing optimization
- **Folium** - Interactive map visualization
- **Pandas** - Data manipulation

### Optimization Algorithm

1. **Geocoding** - Convert addresses to coordinates using Google Maps API
2. **Distance Matrix** - Calculate travel times between all points with batching
3. **Constraint Setup** - Define vehicle capacity and strict time constraints
4. **Smart Redistribution** - OR-Tools automatically redistributes tasks when vehicles exceed time limits
5. **Route Optimization** - Advanced constraint solver with time and capacity dimensions
6. **Solution Validation** - Each vehicle must respect individual working hours
7. **Decision Analysis** - Detailed explanation of vehicle allocation choices
8. **Visualization** - Interactive maps with detailed route visualization

### Intelligent Redistribution Logic

The application uses advanced constraint programming to ensure optimal task distribution:

- **1 Vehicle**: Attempts to complete all tasks, fails if > 600 minutes
- **2 Vehicles**: Automatically redistributes tasks to respect time constraints
- **3 Vehicles**: Uses all vehicles if 2 vehicles cannot complete within time limits
- **Time Constraints**: Each vehicle has individual 600-minute working hours
- **Capacity Constraints**: Each vehicle respects tire capacity limits

## 📊 Results Analysis

The application provides detailed analysis including:

- **Vehicle Summary** - Tires collected, travel time, loading time per vehicle
- **Decision Analysis** - Explanation of why specific number of vehicles was chosen
- **Constraint Summary** - Capacity vs. time constraint analysis
- **Route Details** - Step-by-step route for each vehicle
- **Interactive Map** - Visual representation with different colored routes

## 🔍 Troubleshooting

### Common Issues

1. **Google Maps API errors**
   - Verify API key is correct
   - Check API quotas and billing
   - Ensure Geocoding and Distance Matrix APIs are enabled

2. **No solution found**
   - Reduce number of stops
   - Increase vehicle capacity
   - Extend working hours
   - Check if total tires exceed total capacity

3. **Performance issues**
   - Use async testing for faster results
   - Reduce number of stops for large problems
   - Check internet connection for Google Maps API

### Debug Mode

The application includes built-in debugging:
- Matrix validation and error detection
- Constraint verification
- Detailed error messages
- Fallback distance calculations

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Google Maps Platform** - For geocoding and routing services
- **OR-Tools** - For vehicle routing optimization
- **Streamlit** - For the web application framework
- **Folium** - For interactive map visualization

## 🚀 Deployment

### Streamlit Cloud (Recommended)
1. Push code to GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect GitHub and select repository
4. Configure environment variables: `GOOGLE_API_KEY`
5. Deploy with one click!

### Heroku
1. Install Heroku CLI
2. Deploy: `heroku create your-app-name`
3. Set environment variables: `heroku config:set GOOGLE_API_KEY=your_key`

### Local Development
```bash
git clone https://github.com/Odelf18/TruckRoadOptimizer.git
cd TruckRoadOptimizer
pip install -r requirements.txt
streamlit run app.py
```

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the application logs
3. Create an issue in the repository
4. Contact the development team

---

**Happy optimizing! 🚚✨**

*Built with ❤️ using Streamlit, Google Maps API, and OR-Tools*
