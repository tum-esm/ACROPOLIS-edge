CREATE TABLE IF NOT EXISTS sensors (
    sensor_identifier TEXT NOT NULL,
    creation_timestamp TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (sensor_identifier)
);