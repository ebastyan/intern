-- scripts/migrations/003_create_weather_oradea.sql
CREATE TABLE IF NOT EXISTS weather_oradea (
  date DATE PRIMARY KEY,
  -- Temperature (Celsius)
  temp_max NUMERIC(5,2),
  temp_min NUMERIC(5,2),
  temp_mean NUMERIC(5,2),
  apparent_temp_max NUMERIC(5,2),
  apparent_temp_min NUMERIC(5,2),
  apparent_temp_mean NUMERIC(5,2),
  -- Precipitation
  precipitation_sum NUMERIC(6,2),
  rain_sum NUMERIC(6,2),
  snowfall_sum NUMERIC(6,2),
  snow_depth_max NUMERIC(5,2),
  precipitation_hours NUMERIC(4,1),
  -- Wind
  wind_speed_max NUMERIC(5,2),
  wind_gusts_max NUMERIC(5,2),
  wind_direction_dominant INT,
  -- Radiation / sun
  shortwave_radiation_sum NUMERIC(6,2),
  sunshine_duration NUMERIC(7,1),
  daylight_duration NUMERIC(7,1),
  et0_evapotranspiration NUMERIC(5,2),
  -- Derived from hourly aggregation
  pressure_mean NUMERIC(6,2),
  humidity_mean NUMERIC(4,1),
  cloudcover_mean NUMERIC(4,1),
  -- WMO weather code
  weather_code INT,
  fetched_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_weather_date ON weather_oradea(date);
