# flake8: noqa: E501
#!/usr/bin/env python3
"""
Firebase Service Account Key Converter

This script converts a Firebase service account JSON file to a properly escaped
single-line string format for use in environment variables.

Usage:
    python convert_firebase_key.py path/to/service-account.json

Output:
    Creates service_account.txt with the properly formatted string
"""

import json
import os
import sys


def convert_firebase_key(json_file_path: str) -> bool:
    """
    Convert Firebase service account JSON to env-ready format.

    Args:
        json_file_path (str): Path to the original Firebase service account JSON file
    """
    try:
        # Check if input file exists
        if not os.path.exists(json_file_path):
            print(f"Error: File '{json_file_path}' not found.")
            return False

        # Read and parse the JSON file
        with open(json_file_path) as file:
            service_account_data = json.load(file)

        # Convert to single-line string with escaped quotes and control characters
        json_string = json.dumps(service_account_data, separators=(",", ":"))

        # Escape quotes and newlines for env file format
        escaped_json = (
            json_string.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
        )

        # Write to output file
        output_file = "service_account.txt"
        with open(output_file, "w") as file:
            file.write(f'FIREBASE_SERVICE_ACCOUNT_KEY="{escaped_json}"')

        print("✅ Successfully converted Firebase service account key!")
        print(f"📁 Output saved to: {output_file}")
        print("📋 Copy the content and add it to your .env file")

        return True

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON file. {str(e)}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"Error: {str(e)}")
        return False


def main() -> None:
    """Main function to handle command line arguments."""
    if len(sys.argv) != 2:
        print(
            "Usage: python convert_firebase_key.py <path-to-service-account.json>"
        )
        print("\nExample:")
        print("  python convert_firebase_key.py ./my-firebase-key.json")
        sys.exit(1)

    json_file_path = sys.argv[1]
    success = convert_firebase_key(json_file_path)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
