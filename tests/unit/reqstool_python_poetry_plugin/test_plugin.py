import os
import tempfile

from reqstool_python_poetry_plugin.plugin import create_dist_folder_if_not_exist


def test_create_dist_folder():
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save the current working directory
        original_cwd = os.getcwd()

        try:
            # Change the current working directory to the temporary directory
            os.chdir(temp_dir)

            # Test the function
            create_dist_folder_if_not_exist()

            # Verify that the "dist" folder exists in the temporary directory
            assert os.path.exists(os.path.join(temp_dir, "dist"))

        finally:
            # Change the current working directory back to the original directory
            os.chdir(original_cwd)
