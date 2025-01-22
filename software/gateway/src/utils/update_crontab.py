import subprocess


def update_sudo_crontab(new_command: str, schedule: str = "* * * * *") -> None:
    """Updates the root user's crontab to include a new command if it's not already present."""
    try:
        # Read the existing root crontab
        result = subprocess.run(["sudo", "crontab", "-l"],
                                capture_output=True,
                                text=True,
                                check=False)
        current_crontab = result.stdout if result.returncode == 0 else ""

        # Check if the command is already in the crontab
        full_command = f"{schedule} {new_command}"
        if full_command in current_crontab:
            print(f"The command '{full_command}' is already in the crontab.")
            return

        # Add the new command
        updated_crontab = current_crontab.strip() + "\n" + full_command + "\n"

        # Write the updated crontab
        subprocess.run(["sudo", "crontab", "-"],
                       input=updated_crontab,
                       text=True,
                       check=True)
        print(f"Successfully added '{full_command}' to the sudo crontab.")

    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to update crontab: {e}")
    except PermissionError:
        raise PermissionError(
            "You need root privileges to update the sudo crontab.")
