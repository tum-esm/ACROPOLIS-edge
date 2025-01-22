import os


def update_host_crontab(new_command: str,
                        schedule: str = "* * * * *",
                        crontab_file: str = "/host_crontabs/root") -> None:
    """
    Updates the host crontab file (root user) from inside the Docker container."""
    try:
        # Check if the crontab directory exists
        if not os.path.exists(crontab_file):
            raise FileNotFoundError(
                f"Crontab file '{crontab_file}' not found. Is the directory mounted?"
            )

        # Read the existing crontab file
        with open(crontab_file, "r") as file:
            current_crontab = file.read()

        # Check if the command is already in the crontab
        full_command = f"{schedule} {new_command}"
        if full_command in current_crontab:
            print(f"The command '{full_command}' is already in the crontab.")
            return

        # Add the new command
        updated_crontab = current_crontab.strip() + "\n" + full_command + "\n"

        # Write back to the crontab file
        with open(crontab_file, "w") as file:
            file.write(updated_crontab)

        print(f"Successfully added '{full_command}' to the host crontab.")

    except Exception as e:
        print(f"Failed to update crontab: {e}")
        raise
