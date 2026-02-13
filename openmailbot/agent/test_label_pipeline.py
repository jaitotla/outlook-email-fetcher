"""
Minimal test for `EmailLabelPipeline` using a single email.
"""
import os
import sys

# Ensure package imports work when running this script directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.label_pipeline import EmailLabelPipeline


def test_single_email():
    email = {
       
      "from": "UMassD College of Engineering <alumni@advancement.umassd.edu>",
      "to": [
        "<ankitgoel2004@gmail.com>"
      ],
      "subject": "Chancellor Fuller shares UMD's momentum",
      "body": "Web Version:"
    }

    pipeline = EmailLabelPipeline(openai_api_key=None)
    label = pipeline.label_email(email)
    print(f"Single-email label: {label}")
    return label


if __name__ == "__main__":
    test_single_email()
