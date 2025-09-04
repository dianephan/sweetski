import os
import json
import re
import datetime
import ldclient
from ldclient import Context
from ldclient.config import Config
from ldai.client import LDAIClient, AIConfig, ModelConfig, ProviderConfig, LDMessage
from ldai.tracker import TokenUsage
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from dotenv import load_dotenv

sdk_key = os.getenv('LAUNCHDARKLY_SDK_KEY')

# Set config_key to the AI Config key you want to evaluate.
# the key on the RHS of the dashboard is the key of the AI Config key 
ai_config_key = os.getenv('LAUNCHDARKLY_AI_CONFIG_KEY', 'diary-ai')

def parse_coordinates(ai_response):
    """Parse coordinates from the AI response string"""
    # Find content between brackets
    start_bracket = ai_response.find("{")
    end_bracket = ai_response.find("}")
    if start_bracket != -1 and end_bracket != -1:
        # Extract and split the coordinates
        coords_str = ai_response[start_bracket + 1:end_bracket]
        lat_str, lon_str = coords_str.split(",")
        # Convert to float and clean up any whitespace
        latitude = float(lat_str.strip())
        longitude = float(lon_str.strip())
        coordinates = {"latitude": latitude, "longitude": longitude}
    else:
        coordinates = None
    return coordinates

def save_response_to_json(user_input, ai_response):
    """Save user input and AI response with coordinates to JSON in a single line"""
    
    # Parse coordinates from the AI response string
    parsed_coordinates = parse_coordinates(ai_response)
    print("parsed_coordinates: ", parsed_coordinates)
    
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "url": user_input,
        "ai_response": ai_response,
        "latitude": parsed_coordinates["latitude"] if parsed_coordinates else None,
        "longitude": parsed_coordinates["longitude"] if parsed_coordinates else None,
    }
    
    with open('responses.json', 'a') as f:
        json.dump(entry, f)
        f.write('\n')  # Add newline for each JSON entry

def map_provider_to_langchain(provider_name):
    """Map LaunchDarkly provider names to LangChain provider names."""
    # Add any additional provider mappings here as needed.
    provider_mapping = {
        'gemini': 'google_genai'
        # 'gemini': 'langchain-google-genai'
    }
    print("provider_mapping: ", provider_mapping)
    lower_provider = provider_name.lower()
    return provider_mapping.get(lower_provider, lower_provider)

def track_langchain_metrics(tracker, func):
    """
    Track LangChain-specific operations.

    This function will track the duration of the operation, the token
    usage, and the success or error status.

    If the provided function throws, then this method will also throw.

    In the case the provided function throws, this function will record the
    duration and an error.

    A failed operation will not have any token usage data.

    :param tracker: The LaunchDarkly tracker instance.
    :param func: Function to track.
    :return: Result of the tracked function.
    """
    try:
        result = tracker.track_duration_of(func)
        tracker.track_success()
        if hasattr(result, "usage_metadata") and result.usage_metadata:
            # Extract token usage from LangChain response
            usage_data = result.usage_metadata
            token_usage = TokenUsage(
                input=usage_data.get("input_tokens", 0),
                output=usage_data.get("output_tokens", 0),
                total=usage_data.get("total_tokens", 0) # LangChain also has values for input_token_details { cache_creation, cache_read }
            )
            tracker.track_tokens(token_usage)
    except Exception:
        tracker.track_error()
        raise

    return result

# Initialize LaunchDarkly client
def init_ld_client():
    if not sdk_key:
        raise ValueError("*** Please set the LAUNCHDARKLY_SDK_KEY env first")
    if not ai_config_key:
        raise ValueError("*** Please set the LAUNCHDARKLY_AI_CONFIG_KEY env first")

    ldclient.set_config(Config(sdk_key))
    if not ldclient.get().is_initialized():
        raise ValueError("*** SDK failed to initialize. Please check your internet connection and SDK credential.")
    
    aiclient = LDAIClient(ldclient.get())
    print("*** SDK successfully initialized")
    return aiclient

def get_ai_response(user_input, user_id="example-user", user_name="Anonymous"):
    aiclient = init_ld_client()
    """Handle AI interaction with LaunchDarkly configuration"""
    DEFAULT_SYSTEM_MESSAGE = "You are a helpful assistant that can answer questions and help with tasks."
    
    # Create user context
    context = (
        Context
        .builder('example-user-key')
        .kind('user')
        .name('Sandy')
        .build()
    )

    # Default AI configuration
    default_value = AIConfig(
        enabled=True,
        model=ModelConfig(name='gpt-4o', parameters={}),
        provider=ProviderConfig(name='openai'),

        messages=[LDMessage(role='system', content=DEFAULT_SYSTEM_MESSAGE)],
    )

    # # Optionally, you can use a disabled AIConfig
    # default_value = AIConfig(
    #     enabled=False
    # )
    
    config_value, tracker = aiclient.config(
        ai_config_key,
        context,
        default_value,
        {'myUserVariable': "Testing Variable"}
    )
    
    if not config_value.enabled:
        print("AI Config is disabled")
        return

    try:
        # Create LangChain model instance using init_chat_model
        # Map the provider from config_value to LangChain format
        print("Model config:", config_value.model.__dict__)
        print("Provider config:", config_value.provider.__dict__)
        langchain_provider = map_provider_to_langchain(config_value.provider.name)
        print("Mapped provider:", langchain_provider)
        
        try:
            llm = init_chat_model(
                model=config_value.model.name,
                model_provider=langchain_provider,
            )
            # print("LLM initialized successfully:", llm)
        except Exception as model_init_error:
            print("Error initializing LLM:", str(model_init_error))
            raise
        
        # Prepare messages
        # print("Config messages:", config_value.messages)
        
        # Convert messages to LangChain format
        langchain_messages = []
        for message in (config_value.messages or []):
            msg_dict = message.to_dict()
            if msg_dict['role'] == 'system':
                langchain_messages.append(SystemMessage(content=msg_dict['content']))
            elif msg_dict['role'] == 'assistant':
                langchain_messages.append(AIMessage(content=msg_dict['content']))
            elif msg_dict['role'] == 'user':
                langchain_messages.append(HumanMessage(content=msg_dict['content']))
        
        # Add the new user message
        langchain_messages.append(HumanMessage(content=user_input))
                
        # Get AI response
        completion = track_langchain_metrics(tracker, lambda: llm.invoke(langchain_messages))
        ai_response = completion.content

        # print statement is not working
        return {"response": ai_response, "model": config_value.model.name, "provider": config_value.provider.name}

    except Exception as e:
        return {"error": str(e)}

