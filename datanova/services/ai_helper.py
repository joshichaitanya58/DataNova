import os
import json
import logging

logger = logging.getLogger(__name__)
from flask import session
from database.db_connector import get_db_connection


def extract_json_from_text(text: str):
    """
    Safely cleans markdown code blocks and parses raw text into a Python dict or list.
    """
    if not text:
        return None

    cleaned = text.strip()

    # Strip markdown code fences if present (e.g. ```json ... ```)
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # 1. Try direct JSON parsing
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 2. Try locating curly braces `{ ... }`
    start_brace = cleaned.find("{")
    end_brace = cleaned.rfind("}")
    if start_brace != -1 and end_brace > start_brace:
        try:
            return json.loads(cleaned[start_brace:end_brace + 1])
        except Exception:
            pass

    # 3. Try locating square brackets `[ ... ]`
    start_bracket = cleaned.find("[")
    end_bracket = cleaned.rfind("]")
    if start_bracket != -1 and end_bracket > start_bracket:
        try:
            return json.loads(cleaned[start_bracket:end_bracket + 1])
        except Exception:
            pass

    return None


def make_http_request(url: str, headers: dict = None, payload: dict = None, timeout: int = 20):
    """
    Sends HTTP POST request using `requests` package if installed, else `urllib.request`.
    """
    default_headers = {"User-Agent": "DataNova-Analytics-Platform/1.0"}
    req_headers = {**default_headers, **(headers or {})}
    req_payload = payload or {}

    try:
        import requests
        resp = requests.post(url, headers=req_headers, json=req_payload, timeout=timeout)
        if resp.status_code >= 400:
            raise ValueError(f"HTTP {resp.status_code}: {resp.text}")
        return resp.json()
    except ImportError:
        import urllib.request
        import urllib.error

        json_data = json.dumps(req_payload).encode("utf-8")
        req = urllib.request.Request(url, data=json_data, headers=req_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                res_body = response.read().decode("utf-8")
                return json.loads(res_body)
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8")
            raise ValueError(f"HTTP {http_err.code}: {err_body}")
        except Exception as e:
            raise ValueError(f"HTTP request failed: {str(e)}")


def log_ai_provider_call(provider_name, status):
    """
    Logs an individual AI provider call attempt to the database.
    This is called from within the AI helper to track each attempt in the fallback chain.
    """
    user_id = session.get('id')
    if not user_id:
        logger.warning("Could not log AI provider call: No user in session.")
        return

    conn = get_db_connection()
    if not conn:
        logger.error("Could not log AI provider call: Database connection failed.")
        return

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO api_usage_logs (user_id, endpoint, status, is_ai_call) VALUES (%s, %s, %s, %s)",
                (user_id, f"ai_provider:{provider_name}", status, True)
            )
        conn.commit()
    finally:
        conn.close()


def call_groq(prompt: str, expect_json: bool = False) -> str:
    """
    Provider 1: Groq API Call
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key.startswith("your_"):
        raise ValueError("GROQ_API_KEY environment variable is not configured.")

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Try official groq SDK first if available
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        params = {
            "messages": [{"role": "user", "content": prompt}],
            "model": model,
        }
        if expect_json:
            params["response_format"] = {"type": "json_object"}
        completion = client.chat.completions.create(**params)
        return completion.choices[0].message.content
    except Exception as sdk_err:
        logger.warning(f"Groq SDK failed: {sdk_err}. Falling back to HTTP API.")
        # Fallback to direct HTTP API call if SDK fails
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "model": model
        }
        if expect_json:
            payload["response_format"] = {"type": "json_object"}
        res = make_http_request(url, headers=headers, payload=payload)
        return res["choices"][0]["message"]["content"]


def call_openrouter(prompt: str, expect_json: bool = False) -> str:
    """
    Provider 2: OpenRouter API (DeepSeek free model fallback)
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key.startswith("your_"):
        raise ValueError("OPENROUTER_API_KEY environment variable is not configured.")

    model = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1:free")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://datanova.local",
        "X-Title": "DataNova Analytics Platform"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }
    if expect_json:
        payload["response_format"] = {"type": "json_object"}

    res = make_http_request(url, headers=headers, payload=payload)
    return res["choices"][0]["message"]["content"]


def call_cloudflare(prompt: str, expect_json: bool = False) -> str:
    """
    Provider: Cloudflare Workers AI API
    """
    api_token = os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CF_API_TOKEN")
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID")

    if not api_token or api_token.startswith("your_"):
        raise ValueError("CLOUDFLARE_API_TOKEN environment variable is not configured.")
    
    if not account_id or account_id.startswith("your_"):
        raise ValueError("CLOUDFLARE_ACCOUNT_ID environment variable is not configured.")

    # Default Cloudflare Llama 3 8B Instruct model
    model = os.getenv("CLOUDFLARE_MODEL", "@cf/meta/llama-3-8b-instruct")
    
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    # Prompt JSON requirement handling
    full_prompt = prompt
    if expect_json:
        full_prompt += "\n\nReturn response ONLY as valid JSON."

    payload = {
        "messages": [
            {"role": "user", "content": full_prompt}
        ]
    }

    try:
        res = make_http_request(url, headers=headers, payload=payload)
        
        # Cloudflare Response Format: {"result": {"response": "..."}, "success": true, ...}
        if isinstance(res, dict) and res.get("success", False):
            result = res.get("result", {})
            if "response" in result:
                return result["response"]
            elif "output" in result:
                return result["output"]

        # Fallback handling for unexpected response structure
        if isinstance(res, dict) and "result" in res and isinstance(res["result"], str):
            return res["result"]

        raise ValueError(f"Cloudflare AI unexpected response format: {res}")

    except Exception as e:
        logger.error(f"Cloudflare Workers AI request failed: {e}")
        raise

def call_together(prompt: str, expect_json: bool = False) -> str:
    """
    Provider 4: Together AI API
    """
    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key or api_key.startswith("your_"):
        raise ValueError("TOGETHER_API_KEY environment variable is not configured.")

    model = os.getenv("TOGETHER_MODEL", "mistralai/Mixtral-8x7B-Instruct-v0.1")
    url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }
    if expect_json:
        payload["response_format"] = {"type": "json_object"}

    res = make_http_request(url, headers=headers, payload=payload)
    return res["choices"][0]["message"]["content"]


def call_gemini(prompt: str, expect_json: bool = False) -> str:
    """
    Provider 5: Google AI Studio Gemini API
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key.startswith("your_"):
        raise ValueError("GEMINI_API_KEY environment variable is not configured.")

    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    if model.startswith("models/"):
        model = model.replace("models/", "")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}

    formatted_prompt = prompt
    if expect_json:
        formatted_prompt = f"Always respond in strict valid JSON format.\n\n{prompt}"

    payload = {
        "contents": [
            {"parts": [{"text": formatted_prompt}]}
        ]
    }
    if expect_json:
        payload["generationConfig"] = {
            "responseMimeType": "application/json"
        }

    try:
        res = make_http_request(url, headers=headers, payload=payload)
    except Exception as e:
        # If the error suggests that responseMimeType is not supported, retry without it
        if "responseMimeType" in str(e) and expect_json:
            logger.warning(f"Gemini API rejected responseMimeType, retrying without it. Error: {e}")
            # Remove the generationConfig and retry
            payload.pop("generationConfig", None)
            res = make_http_request(url, headers=headers, payload=payload)
        else:
            raise

    candidates = res.get("candidates", [])
    if candidates and "content" in candidates[0]:
        parts = candidates[0]["content"].get("parts", [])
        if parts and "text" in parts[0]:
            return parts[0]["text"]

    raise ValueError(f"Gemini API returned unexpected structure: {res}")


# Providers registry in fallback priority order
PROVIDERS = [
    ("Groq", call_groq),
    ("OpenRouter (DeepSeek)", call_openrouter),
    ("Cloudflare AI", call_cloudflare),
    ("Together AI", call_together),
    ("Google AI Studio (Gemini)", call_gemini),
]


def generate_ai_completion(prompt: str, expect_json: bool = False):
    """
    Executes AI completion trying configured providers in sequence.
    If expect_json=True, extracts and returns parsed Python dict/list.
    """
    last_errors = []

    for provider_name, provider_fn in PROVIDERS:
        try:
            logger.info(f"[AI Engine] Attempting provider: {provider_name}")
            raw_text = provider_fn(prompt, expect_json=expect_json)
            if not raw_text or not str(raw_text).strip():
                raise ValueError("Empty response received.")

            if expect_json:
                parsed_json = extract_json_from_text(raw_text)
                if parsed_json is not None:
                    logger.info(f"[AI Engine] Success using provider: {provider_name}")
                    log_ai_provider_call(provider_name, 'success')
                    print(f"[AI Engine] Successfully generated response using provider: {provider_name}")
                    return parsed_json
                else:
                    raise ValueError(f"Provider {provider_name} returned unparseable JSON response: {str(raw_text)[:120]}...")
            else:
                logger.info(f"[AI Engine] Success using provider: {provider_name}")
                log_ai_provider_call(provider_name, 'success')
                print(f"[AI Engine] Successfully generated response using provider: {provider_name}")
                return str(raw_text).strip()

        except Exception as err:
            err_msg = f"{provider_name}: {err}"
            logger.warning(f"[AI Engine Warning] Provider failed - {err_msg}")
            log_ai_provider_call(provider_name, 'failure')
            print(f"[AI Engine Warning] Provider failed - {err_msg}")
            last_errors.append(err_msg)

    combined_err = " | ".join(last_errors)
    raise RuntimeError(f"All AI providers failed. Error breakdown: {combined_err}")