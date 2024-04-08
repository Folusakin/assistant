#weather.py

import aiohttp
import asyncio
import sys
from datetime import datetime
import time
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text as sa_text
from openai import AsyncOpenAI
from configure import custom_weather_prompt_template

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")  # Redacted and replaced with os.environ.get
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")  # Redacted and replaced with os.environ.get

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class WeatherAPI:
    WEATHER_BASE_URL = 'https://api.weather.gov/points/'

    def __init__(self, db_url='sqlite+aiosqlite:///uscities.db', api_key=WEATHER_API_KEY):
        self.engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
        self.Session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.api_key = api_key
        self.gpt_client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url='https://api.groq.com/openai/v1',)#using groq for speed up

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    async def close(self):
        if hasattr(self, 'client_session'):
            await self.client_session.close()
        await self.engine.dispose()

    async def fetch_lat_lng_by_city_state(self, city, state):
        try:
            query_template = """SELECT lat, lng FROM uscities WHERE city_ascii=:city AND {}=:state"""
            query_column = "state_id" if len(state) == 2 and state.isupper() else "state_name"
            query = sa_text(query_template.format(query_column))

            async with self.Session() as session:
                result = await session.execute(query, {"city": city, "state": state})
                city_data = result.fetchone()
                if city_data:
                    return {'latitude': city_data.lat, 'longitude': city_data.lng}
                return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    async def fetch_weather_by_coords(self, latitude, longitude):
        try:
            # Step 1: Get gridId, gridX, and gridY
            point_url = f'https://api.weather.gov/points/{latitude},{longitude}'
            async with self.client_session.get(point_url, headers={"User-Agent": "MyWeatherApp"}, timeout=7) as response:
                response.raise_for_status()
                grid_data = await response.json()
                gridId = grid_data['properties']['gridId']
                gridX = grid_data['properties']['gridX']
                gridY = grid_data['properties']['gridY']

                # Step 2: Construct URL for hourly forecast using gridId, gridX, gridY
                forecast_hourly_url = f'https://api.weather.gov/gridpoints/{gridId}/{gridX},{gridY}/forecast/hourly'

                # Step 3: Fetch the hourly forecast data
                async with self.client_session.get(forecast_hourly_url, headers={"User-Agent": "MyWeatherApp"}, timeout=10) as forecast_response:
                    forecast_response.raise_for_status()
                    weather_data = await forecast_response.json()
                    return self.clean_weather_data(weather_data)
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def clean_weather_data(weather_data):
        cleaned_data = []
        wind_direction_full_names = {
            'N': 'North', 'NE': 'North East', 'E': 'East', 'SE': 'South East',
            'S': 'South', 'SW': 'South West', 'W': 'West', 'NW': 'North West'
        }

        for index, period in enumerate(weather_data['properties']['periods']):
            if index % 2 == 0:
                start_time_iso = period['startTime']
                end_time_iso = period['endTime']

                start_time_obj = datetime.fromisoformat(start_time_iso[:-6]) 
                end_time_obj = datetime.fromisoformat(end_time_iso[:-6])

                start_date_formatted = start_time_obj.strftime('%d %B, %Y')
                start_time_formatted = f"{start_time_obj.strftime('%I %p').lstrip('0')} on {WeatherDataProcessor.ordinal_date(start_time_obj)}"
                end_time_formatted = f"{end_time_obj.strftime('%I %p').lstrip('0')} on {WeatherDataProcessor.ordinal_date(end_time_obj)}"

                day_of_week = start_time_obj.strftime('%A')
                is_daytime = period['isDaytime']
                temperature = period['temperature']
                get_temperature_unit = period['temperatureUnit']
                short_forecast = period['shortForecast']
                probability_of_precipitation = period.get('probabilityOfPrecipitation', {}).get('value', 'N/A')  
                wind_speed = period['windSpeed']
                wind_direction = period['windDirection']
                relative_humidity = period.get('relativeHumidity', {}).get('value', 'N/A')  
                temperature_trend = period.get('temperatureTrend', 'N/A')  

                wind_direction_full = wind_direction_full_names.get(wind_direction, wind_direction)  

                if get_temperature_unit == 'F':
                    temperature_unit = "Fahrenheit"
                else:
                    temperature_unit = "Celsius"

                cleaned_data.append(f"Day of the Week: {day_of_week}\n"
                                    f"Start Time: {start_time_formatted}, End Time: {end_time_formatted}\n"
                                    f"Daytime: {is_daytime}\n"
                                    f"Temperature: {temperature} {temperature_unit}\n"  
                                    f"Short Forecast: {short_forecast}\n"
                                    f"Probability of Precipitation: {probability_of_precipitation}%\n"
                                    f"Wind: {wind_speed} from {wind_direction_full}\n"
                                    f"Relative Humidity: {relative_humidity}%\n"
                                    f"Temperature Trend: {temperature_trend}\n"  
                                    + "-" * 5 + "\n") 

        return '\n'.join(cleaned_data)

    @staticmethod
    def ordinal_date(date_obj):
        return date_obj.strftime("%d").lstrip('0') + {1: 'st', 2: 'nd', 3: 'rd'}.get(4 if 10 <= date_obj.day <= 20 else date_obj.day % 10, "th") + " " + date_obj.strftime("%B, %Y")

    async def generate_custom_weather_prompt(self, weather_info, query):
        custom_prompt = custom_weather_prompt_template.format(query=query)
        return f"{weather_info} {custom_prompt}"

    async def process_weather_query(self, city, state, query):
        await self.init_client_session()  
        coords = await self.fetch_lat_lng_by_city_state(city, state)

        if coords:
            location_directive = ''.join([" Currently: looking at ", city, ", ", state, "->"])
            weather_data = await self.fetch_weather_by_coords(**coords)
            prompt = await self.generate_custom_weather_prompt(weather_info=location_directive + str(weather_data), query=query)

            start_time = asyncio.get_event_loop().time()  

            response = await self.gpt_client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=[{"role": "user", "content": prompt}], 
                temperature=0.5,
                stream=False,
            )

            end_time = asyncio.get_event_loop().time()  
            print(f"OpenAI API call took {end_time - start_time:.2f} seconds")  

            if response.choices:
                print(response.choices[0].message.content)
                result = {"weather_query": query, "weather_tool_response_needing_interpretation": response.choices[0].message.content}
            else:
                result = {"weather_query": query, "weather_tool_response_needing_interpretation": "That is currently unavailable."}
            return result
        else:
            result = {"weather_query": query, "weather_tool_response_needing_interpretation": "City coordinates not found."}
            return result

async def main():
    initial_time = time.perf_counter()

    tasks_info = [
        ('San Francisco', 'California', "When is the coldest and warmest day?"),  
        ('New York', 'New York', "On what days am I likely to need my umbrella?"),
        ('Boise', 'Idaho', "what's the actual temperature?"),
    ]

    async with WeatherAPI() as unified_api:
        tasks = [unified_api.process_weather_query(city, state, query) for city, state, query in tasks_info]
        results = await asyncio.gather(*tasks)
        for result in results:
            print(result)

    print("Total time taken: ", time.perf_counter() - initial_time)

if __name__ == "__main__":
    asyncio.run(main())