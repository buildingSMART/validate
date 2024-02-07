(TBC - dev-v0.6-alpha)

# IFC Validation Service

A comprehensive solution integrating a React frontend with a Python backend using the Django framework. This software is designed to facilitate various validation checks including bsdd-check, syntax check, schema check, and gherkin-rules check.
## Getting Started

### Installation

1. Clone the repository to your local machine.
2. Navigate to the root directory of the project.
3. Run the following command to build and start the application:
   ``````
   docker-compose up --build
   ``````

This command assembles the application, installs all required packages and submodules, and starts the local server.

## Application Structure

The application consists of three main submodules, each hosted in separate GitHub repositories. Docker Compose is configured to automatically bind the correct submodule versions for local deployment.

### Submodules

Documentation of the seperate functionalities can be found within each submodule. d

1. **File Parser**: A module within IfcOpenShell, dedicated to parsing files. https://github.com/IfcOpenShell/step-file-parser
2. **Gherkin Rules**: Contains the rules for validation. It can be run independently by cloning the repository and executing:
https://github.com/buildingSMART/ifc-gherkin-rules

   ```
   pytest -sv
   ```

   Debugging individual rules is supported with commands like:

    ``````
   python test/test_main.py alb001 # For a single rule
   python test/test_main.py alb001 alb002 # For multiple rules
   python test/test_main.py path_to_separate_file.py # For a separate file
   ``````

3. **Shared DataModel**: This module includes Django data models shared between the main repository and the Gherkin repository, serving as a submodule for both.
https://github.com/buildingSMART/ifc-validation-data-model

## Running Validation Checks

The application supports multiple validation checks on one or multiple IFC files that can be run separately:

- BSDD-Check
- Syntax Check
- Schema Check
- Gherkin-Rules Check


## Contributing

Contributions are welcome! For major changes, please open an issue first to discuss what you would like to change. Ensure to update tests as appropriate.

### Creating Pull Requests

1. Fork the repository.
2. Create your feature branch (git checkout -b feature/AmazingFeature).
3. Commit your changes (git commit -am 'Add some AmazingFeature').
4. Push to the branch (git push origin feature/AmazingFeature).
5. Open a pull request.