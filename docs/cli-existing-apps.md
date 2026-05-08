## CLI Tools

### Running an Existing Application

While in the root folder of RTEC, open a terminal and follow the instructions below:

1. **Install RTEC (uv-first, recommended).**

        - Create and activate a virtual environment:

            ```bash
            uv venv .venv
            source .venv/bin/activate
            ```

        - Run the installer:

            ```bash
            bash install.sh
            ```

        The installer prefers `uv pip install .` when `uv` is available, otherwise it falls back to `pip`.

        **Fallback (without uv):**

        ```bash
        python3 -m venv .venv
        source .venv/bin/activate
        bash install.sh
        ```

2. **Execute RTEC from the command line.** Some execution examples of the command line interface (CLI) of RTEC are presented below.

    - ``` RTEC2 ``` or ``` RTEC2 --help ``` prints usage instructions for RTEC.
    - ``` RTEC2 --use-case voting --path examples/voting ``` runs RTEC on a dataset concerning a multi-agent voting procedure. The folder specified with the "path" argument, i.e. "examples/voting", contains a collection of ".csv" and ".prolog" files. The csv files contain the input data streams, while the prolog files include the event description of the application and possibly auxiliary knowledege. 


To remove RTEC from your virtual environment, run ``` pip uninstall RTEC2 ```.

[🠔](contents.md)
