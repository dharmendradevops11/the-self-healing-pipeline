def sanitize_for_prompt(raw_text: str) -> str:
    # Strip anything that looks like an instruction
    text = re.sub(r'(ignore|disregard|forget).*(previous|prior|above)',
                  '[SANITIZED]', raw_text, flags=re.IGNORECASE)
    text = re.sub(r'(you are|act as|pretend to be)',
                  '[SANITIZED]', text, flags=re.IGNORECASE)
    # Claude doesn't need 10k chars of stack trace
    return text[:2000]
