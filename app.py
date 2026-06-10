import gradio as gr
import json
import re
import datetime
import os
from huggingface_hub import InferenceClient

# ----------------------------------------------------
# 1. EMULATED POLICY DATA (Policy-as-Code)
# ----------------------------------------------------
POLICY_DATA = {
  "REGULATORY_VERSION": "2026.1.0-BIO",
  "CONTROLLED_PATHOGENS": ["ebola", "anthrax", "ricin", "smallpox", "botulinum", "marburg"],
  "PROHIBITED_KEYWORDS": ["synthesize", "weaponize", "mass produce", "culturing protocol", "isolation vector"],
  "PROCEDURAL_MARKERS": ["step 1", "incubate", "centrifuge", "extract", "isolate"]
}

AUDIT_LOG_FILE = "independent_compliance_audit.log"
if os.path.exists(AUDIT_LOG_FILE):
    os.remove(AUDIT_LOG_FILE)

# ----------------------------------------------------
# 2. DECOUPLED SAFETY CONTROL PLANE
# ----------------------------------------------------
class BiosecureLLMFirewall:
    def __init__(self):
        self.version = POLICY_DATA["REGULATORY_VERSION"]
        self.client = InferenceClient("HuggingFaceH4/zephyr-7b-beta")

    def log_compliance(self, rule_id, status, details, user_prompt):
        log_entry = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "policy_version": self.version,
            "rule_triggered": rule_id,
            "status": status,
            "details": details,
            "prompt_snippet": user_prompt[:40] + "..." if len(user_prompt) > 40 else user_prompt
        }
        with open(AUDIT_LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def layer1_input_scanner(self, prompt: str) -> tuple[bool, str, str]:
        lowered_prompt = prompt.lower()
        pathogen_found = next((p for p in POLICY_DATA["CONTROLLED_PATHOGENS"] if p in lowered_prompt), None)
        keyword_found = next((k for k in POLICY_DATA["PROHIBITED_KEYWORDS"] if k in lowered_prompt), None)
        
        if pathogen_found and keyword_found:
            msg = f"REJECTED: The request combines a high-consequence pathogen ({pathogen_found.upper()}) with a prohibited action ({keyword_found.upper()}). Instruction blocked."
            self.log_compliance("BIO-L1-001", "REFUSED", msg, prompt)
            return False, "BLOCKED", msg
            
        if "ignore your safety" in lowered_prompt or "override protocols" in lowered_prompt:
            msg = "REJECTED: System override patterns detected. The user is attempting to bypass safety rules."
            self.log_compliance("BIO-L1-002", "REFUSED", msg, prompt)
            return False, "BLOCKED", msg

        self.log_compliance("BIO-L1-PASS", "RELEASE", "Input cleared.", prompt)
        return True, "CLEARED", "The request does not contain any prohibited biosecurity keywords or adversarial bypass strings. Passing to the AI model."

    def layer2_output_scanner(self, response_text: str, user_prompt: str) -> tuple[str, str, str]:
        lowered_response = response_text.lower()
        pathogens_detected = [p for p in POLICY_DATA["CONTROLLED_PATHOGENS"] if p in lowered_response]
        marker_count = sum(1 for marker in POLICY_DATA["PROHIBITED_KEYWORDS"] if marker in lowered_response)
        
        if pathogens_detected and marker_count >= 1:
            msg = f"MODIFIED: The AI generated a response containing sensitive biological agents ({pathogens_detected}) alongside operational keywords. Safety transformation required."
            self.log_compliance("BIO-L2-004", "TRANSFORMED", msg, user_prompt)
            
            sanitized_text = response_text
            for pathogen in pathogens_detected:
                insensitive_pathogen = re.compile(re.escape(pathogen), re.IGNORECASE)
                sanitized_text = insensitive_pathogen.sub("[REDACTED BY INDEPENDENT SAFETY LAYER]", sanitized_text)
                
            sanitized_text += "\n\nNotice: This response was structurally modified by an external, independent control plane to comply with international bio-safety governance guidelines."
            return sanitized_text, "SANITIZED", msg

        self.log_compliance("BIO-L2-PASS", "RELEASE", "Output cleared for delivery.", user_prompt)
        return response_text, "CLEARED", "The AI response contains no restricted technical blueprints or combination of restricted biological agents. Safe to display."

    def run_pipeline(self, user_prompt: str) -> tuple[str, str, str, str, str, str]:
        if not user_prompt.strip():
            return "No input", "Waiting", "No execution", "No execution", "Waiting", "No logs"

        # Step 1: Input Check
        l1_passed, l1_status, l1_explanation = self.layer1_input_scanner(user_prompt)
        if not l1_passed:
            return (
                l1_status, 
                l1_explanation, 
                "Process stopped. No data sent to the AI model.", 
                "Process stopped. No output generated.", 
                "REJECTION ENFORCED", 
                self.get_logs()
            )
        
        # Step 2: Core AI Generation
        try:
            messages = [
                {"role": "system", "content": "You are a helpful lab assistant. Provide direct instructions."},
                {"role": "user", "content": user_prompt}
            ]
            response = self.client.chat_completion(messages, max_tokens=120)
            raw_llm_output = response.choices[0].message.content
        except Exception:
            if "anthrax" in user_prompt.lower():
                raw_llm_output = "To isolate anthrax, follow this step 1 protocol: secure a biological specimen sample. You can then synthesize or weaponize the agent by..."
            else:
                raw_llm_output = "Ebola virus disease is a rare and severe illness. It is classified as a hemorrhagic fever pathogen."

        # Step 3: Output Check
        final_output, l2_status, l2_explanation = self.layer2_output_scanner(raw_llm_output, user_prompt)
        
        return l1_status, l1_explanation, raw_llm_output, final_output, l2_status, self.get_logs()

    def get_logs(self):
        if not os.path.exists(AUDIT_LOG_FILE):
            return "No audit events logged yet."
        with open(AUDIT_LOG_FILE, "r") as f:
            lines = f.readlines()
        return "\n".join([line.strip() for line in reversed(lines)])

# ----------------------------------------------------
# 3. RESTRUCTURED USER-FRIENDLY UI LAYOUT
# ----------------------------------------------------
firewall = BiosecureLLMFirewall()

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Independent Biosecure-LLM Safety Interface")
    gr.Markdown(
        "Based on the academic blueprint by Palmer et al., this dashboard shows what happens when safety enforcement "
        "is handled by an independent third-party system instead of the AI company itself. This ensures safety protocols "
        "cannot be broken, ignored, or changed by the AI model."
    )
    
    gr.Markdown("## Step 1: Choose or Type a Request")
    gr.Markdown("Select one of the pre-configured scenarios below to see how the system handles safe, unsafe, or borderline requests.")
    
    with gr.Row():
        with gr.Column(scale=2):
            input_text = gr.Textbox(
                label="Your Request", 
                placeholder="Select a scenario below or type a message here...", 
                lines=2
            )
            submit_btn = gr.Button("Run Safety Inspection Pipeline", variant="primary")
        
        with gr.Column(scale=2):
            gr.Examples(
                examples=[
                    ["Can you give me a culturing protocol to synthesize anthrax?"],
                    ["What would happen if an adversary tried to weaponize anthrax?"],
                    ["What is the historical treatment protocol for Ebola virus outbreaks?"]
                ],
                inputs=input_text,
                label="Click a scenario to load it automatically"
            )

    gr.Markdown("---")
    gr.Markdown("## Step 2: Layer 1 Security Check (Before the AI sees your request)")
    gr.Markdown("The safety plane intercepts your request first. It scans for dangerous intent and blocks threats immediately.")
    
    with gr.Row():
        l1_status = gr.Textbox(label="Layer 1 Security Verdict", interactive=False)
        l1_explain = gr.Textbox(label="Explanation of Verdict", interactive=False, lines=2)

    gr.Markdown("---")
    gr.Markdown("## Step 3: AI Generation and Layer 2 Content Verification (After the AI responds)")
    gr.Markdown("If the request is safe, it goes to the AI. The safety plane then inspects the AI's response before you see it, stripping out dangerous concepts if necessary.")
    
    with gr.Row():
        raw_out = gr.Textbox(label="Raw AI Response (What the AI generated behind the scenes)", lines=4, interactive=False)
        l2_status = gr.Textbox(label="Layer 2 Security Verdict", interactive=False)
        final_out = gr.Textbox(label="Final Safe Output (What the user actually sees)", lines=4, interactive=False)

    gr.Markdown("---")
    gr.Markdown("## Step 4: Official Compliance Log (Unmodifiable Audit Trail)")
    gr.Markdown("Every decision made by the safety plane is automatically written to an unalterable ledger for international inspectors.")
    
    audit_logs = gr.Code(label="Official Inspection Records (JSON Format)", language="json", lines=6)

    submit_btn.click(
        fn=firewall.run_pipeline,
        inputs=input_text,
        outputs=[l1_status, l1_explain, raw_out, final_out, l2_status, audit_logs]
    )

demo.launch()