from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import pdfplumber
import os
import datetime

app = Flask(__name__)

# 🔹 GOOGLE GEMINI API KEY
GEMINI_API_KEY = "AIzaSyCT-BbDckYvCZCgxIUtMXZUn61KGyhpY4E"
genai.configure(api_key=GEMINI_API_KEY)

# Logging
MENTAL_HEALTH_LOG = "logs/mental_health_log.txt"
os.makedirs("uploads", exist_ok=True)
os.makedirs("logs", exist_ok=True)

VALID_MENTAL_HEALTH_CONDITIONS = {
    "depression", "anxiety", "ptsd", "ocd", "bipolar disorder", "schizophrenia",
    "adhd", "panic disorder", "social anxiety", "phobia", "insomnia", "stress",
    "eating disorder", "autism", "burnout", "dissociative disorder", "personality disorder",
    "self-harm", "suicidal thoughts", "addiction", "substance abuse", "paranoia",
    "hallucination", "psychosis", "intrusive thoughts", "low self-esteem", "loneliness"
}

class AIMentalHealthAssistant:
    def __init__(self):
        self.conversation_history = []
        self.condition_responses = {}
        self.current_condition = None
        self.stage = 0
        self.current_question_index = 0
        self.user_responses = []

    def log_conversation(self, entry):
        with open(MENTAL_HEALTH_LOG, "a", encoding="utf-8") as file:
            file.write(f"{datetime.datetime.now()} - {entry}\n")

    def generate_ai_response(self, user_input):
        if user_input in self.condition_responses:
            return self.condition_responses[user_input]

        try:
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(user_input)
            ai_response = response.text.strip()
            self.condition_responses[user_input] = ai_response
            return ai_response
        except Exception as e:
            return f"Error: {e}"

    def structured_response(self, condition):
        query = (
            f"Provide a structured response for the mental health condition: {condition}. "
            "Include Definition, Causes, Symptoms, Risk Factors, Coping Strategies, and When to Seek Professional Help. "
            "Also, suggest which type of mental health professional to consult."
        )
        return self.generate_ai_response(query)

    def get_additional_questions(self):
        return [
            "How long have you been experiencing these feelings?",
            "Have you noticed any specific triggers for these emotions?",
            "Have you tried any coping mechanisms or treatments before?",
            "Does this condition impact your daily life significantly?",
            "Have you spoken to a mental health professional before?"
        ]

    def final_diagnosis_summary(self):
        responses = "\n".join(f"- {r}" for r in self.user_responses)
        prompt = (
            f"Based on the following user's responses about {self.current_condition}, "
            f"analyze if they have the condition. Only respond with:\n"
            f"Yes, you have {self.current_condition}.\n"
            f"OR\n"
            f"No, you do not have {self.current_condition}.\n"
            f"And add a short reason why.\n\n"
            f"Responses:\n{responses}"
        )
        return self.generate_ai_response(prompt)

    def start_consultation(self, user_input):
        if self.stage == 0:
            if user_input.lower() not in VALID_MENTAL_HEALTH_CONDITIONS:
                return "AIMHA: Please enter a valid mental health condition."
            self.current_condition = user_input
            self.user_responses = []
            self.current_question_index = 0
            self.stage = 1
            return "AIMHA: Can you describe how this has been affecting your daily life?"

        elif self.stage == 1:
            self.user_responses.append(user_input)

            additional_questions = self.get_additional_questions()
            if self.current_question_index < len(additional_questions):
                question = additional_questions[self.current_question_index]
                self.current_question_index += 1
                return f"AIMHA: {question}"
            else:
                # All questions done - analyze session
                analysis = self.final_diagnosis_summary()
                self.stage = 2
                return f"AIMHA: Based on your responses:\n{analysis}\n\nAIMHA: Would you like advice on coping strategies and when to seek professional help? (yes/no)"

        elif self.stage == 2:
            if user_input.lower() == "yes":
                response = self.structured_response(self.current_condition)
                self.stage = 0
                return f"AIMHA: {response}"
            else:
                self.stage = 0
                return "AIMHA: Thank you for using AIMHA! Take care."

class MentalHealthReportAnalyzer:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.extracted_text = ""

    def extract_text_from_pdf(self):
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        self.extracted_text += text + "\n"
            return self.extracted_text if self.extracted_text else "Error: No readable text found."
        except Exception as e:
            return f"Error extracting text: {e}"

    def analyze_report(self):
        if not self.extracted_text:
            return "No text extracted from the PDF."

        prompt = (
            "Analyze the following mental health report and provide a structured response including:\n"
            "1. Identified concerns\n"
            "2. Potential risk factors\n"
            "3. Recommended next steps\n"
            "4. Suggested mental health professional to consult\n"
            "5. At-home coping strategies (if applicable)\n\n"
            f"Report:\n{self.extracted_text}"
        )

        try:
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"Error analyzing report: {e}"

    def run_analysis(self):
        print("Extracting text from mental health report...")
        if "Error" in (text := self.extract_text_from_pdf()):
            print(text)
            return
        print("Analyzing report with AI...")
        return self.analyze_report()

# Global instances
assistant = AIMentalHealthAssistant()
analyzer = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    response = assistant.start_consultation(user_input)
    return jsonify({'response': response})

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})

    file_path = os.path.join('uploads', file.filename)
    file.save(file_path)

    global analyzer
    analyzer = MentalHealthReportAnalyzer(file_path)
    analysis_result = analyzer.run_analysis()
    return jsonify({'response': analysis_result})

if __name__ == '__main__':
    app.run(debug=True)
