import json
import logging
import argparse
import os
import sys
import csv
from dotenv import load_dotenv
import PyPDF2

# Import your modules (adjust paths if necessary)
from document_loaders.template_loader import load_templates_from_json
from file_operations.saving_result_in_file import save_results
from prompts_operation.prompts_operations import generate_prompts
from utils import split_query_by_length_with_overlap
#python erisaV2.py -i ./input -if erisadoc.pdf -f pdf
# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Helper function to read PDFs
def read_pdf(file_path):
    try:
        text_content = ""
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text_content += page.extract_text() or ''
        return text_content
    except Exception as e:
        logger.error(f"Failed to read PDF file: {file_path}. Error: {e}")
        sys.exit(1)

# Helper function to read text files
def read_text(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger.error(f"Failed to read text file: {file_path}. Error: {e}")
        sys.exit(1)

class ErisaAnalyzer:
    def __init__(self, input_dir, input_filename, file_type):
        self.input_dir = input_dir
        self.input_filename = input_filename
        self.file_type = file_type
        self._load_environment_variables()

    def _load_environment_variables(self):
        if not os.path.exists("MyEnv.env"):
            logger.warning("MyEnv.env file not found! Proceeding with system environment variables.")
        load_dotenv("MyEnv.env")

    def read_input_file(self):
        file_path = os.path.join(self.input_dir, self.input_filename)
        if not os.path.isfile(file_path):
            logger.error(f"Input file does not exist: {file_path}")
            sys.exit(1)

        if self.file_type == 'pdf':
            logger.info(f"Reading PDF file: {file_path}")
            return read_pdf(file_path)
        elif self.file_type == 'txt':
            logger.info(f"Reading text file: {file_path}")
            return read_text(file_path)
        else:
            logger.error(f"Unsupported file type: {self.file_type}")
            sys.exit(1)

    def execute_all_rules(self):
        logger.info(f"Executing analysis for ALL rules in 'erisaRules.json'...")
        try:
            template_prompts = load_templates_from_json("Templates/erisaRules.json")
        except Exception as e:
            logger.error(f"Failed to load template file 'Templates/erisaRules.json'. Error: {e}")
            sys.exit(1)

        query = self.read_input_file()

        # Split the query for large files
        queries = split_query_by_length_with_overlap(query)

        all_results = {}

        for rule_name, template_bdd in template_prompts.items():
            logger.info(f"Processing rule: {rule_name}")
            result_prompt = ""

            if len(queries) == 1:
                result_prompt = generate_prompts(template_bdd, queries[0])
            else:
                for i, chunk in enumerate(queries):
                    result_prompt += f"Document chunk {i+1}:\n{generate_prompts(template_bdd, chunk)}\n\n"

            # Here, assume generate_prompts returns structured data.
            # For demonstration, let’s fake it as:
            all_results[rule_name] = {
                "Rule Definition": result_prompt.strip(),
                "Comply Yes/No": "",
                "Citation": ""
            }

        # Save JSON
        base_filename = os.path.splitext(self.input_filename)[0]
        output_json_filename = f"{base_filename}.json"
        json_output_path = os.path.join(self.input_dir, output_json_filename)

        with open(json_output_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)

        logger.info(f"Analysis complete. JSON results saved to: {json_output_path}")

        # Convert JSON to CSV
        self.convert_json_to_csv(json_output_path)

    def convert_json_to_csv(self, json_file_path):
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                logger.error(f"Unexpected JSON structure. Expected a dictionary at the top level.")
                return

            base_filename = os.path.splitext(os.path.basename(json_file_path))[0]
            csv_filename = f"{base_filename}.csv"
            csv_output_path = os.path.join(self.input_dir, csv_filename)

            # ✅ NEW: Remove existing CSV if it exists to avoid permission errors
            if os.path.exists(csv_output_path):
                try:
                    os.remove(csv_output_path)
                    logger.info(f"Deleted existing CSV file: {csv_output_path}")
                except Exception as e:
                    logger.error(f"Failed to delete existing CSV file: {e}")
                    return

            with open(csv_output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = ['Rule', 'Rule Definition', 'Comply Yes/No', 'Citation']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
                writer.writeheader()

                for rule_name, details in data.items():
                    rule_def = details.get("Rule Definition", "").replace('\r', ' ').replace('\n', ' ').replace('"', '""')
                    comply = details.get("Comply Yes/No", "")
                    citation = details.get("Citation", "")

                    writer.writerow({
                        'Rule': rule_name,
                        'Rule Definition': rule_def,
                        'Comply Yes/No': comply,
                        'Citation': citation
                    })

            logger.info(f"CSV file created: {csv_output_path}")
        except Exception as e:
            logger.error(f"Failed to convert JSON to CSV: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ERISA Analysis for All Rules")
    parser.add_argument("-i", "--input_dir", required=True, help="Input directory containing files")
    parser.add_argument("-if", "--input_filename", required=True, help="Input filename")
    parser.add_argument("-f", "--file_type", required=True, choices=["pdf", "txt"], help="File type to process (pdf or txt)")

    args = parser.parse_args()

    analyzer = ErisaAnalyzer(args.input_dir, args.input_filename, args.file_type)
    analyzer.execute_all_rules()

