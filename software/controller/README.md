# Controller

The `controller` directory contains the **Edge Controller** implementation, which is responsible for managing sensor data acquisition, processing, and local decision-making. This component runs in a **Docker container** and is controlled by the **Edge Gateway**.

## **Directory Structure**

```bash
📁 controller
    📁 config          # Configuration files for the controller
    📁 data            # Local data storage for manual runs
    📁 docker          # Docker setup and build files
    📁 logs            # Local log storage for manual runs
    📁 scripts         # Utility scripts for development and git action
    📁 src             # Edge controller logic implementation
    📁 tests           # Unit and integration tests
    📄 pyproject.toml  # Python project configuration
```

## **Docker Setup**

The **Edge Controller** is containerized using Docker for consistent deployment and execution. The `docker` folder contains a `Dockerfile` that builds the controller logic located in the `src` directory. The **Edge Gateway** is responsible for managing and launching the controller container.

The **Edge Gateway** dynamically builds and runs the controller container using the latest version available from this **Git repository**. It checks if the container is running, stops outdated versions, pulls the correct commit, and builds the image if necessary before launching the new container.

How to build and run the **Edge Controller** manually:

```bash
tba
```

## **Installation (Development Mode)**

For local development, you can set up a virtual environment and install dependencies:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
poetry install
```

Run the **Edge Controller** manually:

```bash
cp config/config.template.json config/config.json
nano config/config.json # Configure and verify "simulation_mode": = true
python src/main.py
```

## **Run mypy Type Check Script**

To ensure type correctness, run the **mypy** type checker:

```bash
chmod +x scripts/run_mypy.sh
scripts/run_mypy.sh
```

<br>

---

For further details, refer to individual subdirectory documentation and `pyproject.toml` settings.
