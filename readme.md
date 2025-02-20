# HyBioML: Hybrid Biosphere ModeL

## Table of Contents
1. [Environment Configuration](#environment-configuration)
2. [Directory Structure](#directory-structure)
3. [Installation](#installation)
4. [Usage](#usage)
5. [Contributing](#contributing)
6. [License](#license)

## Environment Configuration

- **scikit-learn**: v0.22.1 (later versions will throw out warnings)
- **netCDF4**: v1.5.6
- **mpi4py**: v3.0.3 (with gcc/6.3.0 and openmpi/3.0.0)

## Directory Structure

### forcing_data
Site-level forcing including:
- `US-MoT_forcing.nc4`: Morton Arboretum
- `US-MOz_forcing.nc4`: MOFLUX site
- `US-Ho1_forcing.nc4`: Howland Forest flux site
- `US-SPR_forcing.nc4`: SPRUCE

### surfdata
...

## Installation

To set up the environment, follow these steps:

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/HyBioML.git
    cd HyBioML
    ```

2. Create a virtual environment and activate it:
    ```sh
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

## Usage

To run the model, use the following command:
```sh
python run_model.py --config config.yaml