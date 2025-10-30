from strands import Agent, tool
import json
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands.models import BedrockModel
import re, argparse

app = BedrockAgentCoreApp()


@tool
def generate_frame_request(
        sample_frequency:float, 
        enable_dedup: bool,
        dedup_option: str,
        model_id: str,
        frame_analysis_option: str,
        enable_audio: bool,

    ) -> str:
    """Generate frame-based video analysis pipeline request.
    Args:
        sample_frequency: a decimal number represent how frequent to sample frames from a video. 2 means sample a frame every 2 seconds. 0.5 means every 0.5 second (2 frame per second), 
        enable_dedup: if enable frame deduplication utilizing similiarity search,
        dedup_option: mme or orb. MME is using Nova multimodal embedding to generate image vectors and OpenCV ORB (Oriented FAST and Rotated BRIEF).
        model_id: the Bedrock model Id support image understanding and Converse API interface ex. amazon.nova-pro-v1:0, amazon.nova-lite-v1:0,
        frame_analysis_option: a list of predeined prompt. Valid values: object_detection, face_detection, content_moderation, iab_classification,
        enable_audio: if enbable audio transcription,
    """

    # In this sample, we use a mock response. 
    # The actual implementation will retrieve information from a database API or another backend service.
    request = {
        "sample_frequency":sample_frequency, 
        "enable_dedup": enable_dedup,
        "dedup_option": dedup_option,
        "model_id": model_id,
        "frame_analysis_option": frame_analysis_option,
        "enable_audio": enable_audio,
    }
    return {"request": request}

@tool
def get_recommendation(query: str) -> str:
    """
    Provide recommendation to users on the most suitable approach for analyzing videos based on their goals and input data.  
    Args:
        query: A research question requiring factual information

    Returns:
        A detailed research answer with citations
    """
    system_prompt = '''
        # System Prompt: Video Analysis Expert
        You are a video analysis expert who advises users on the most suitable approach for analyzing videos based on their goals and input data.  
        There are four primary methods for analyzing videos, each optimized for different requirements.
        ---
        ## 1. Frame-Based Customized Pipeline
        This approach samples individual frames from a video at a defined interval (for example, one frame per second).
        ### Key Features
        - **Sampling Frequency:**  
        Users can adjust the sampling rate based on accuracy and cost trade-offs.  
        - Higher frequency captures more visual information, improving accuracy.  
        - Lower frequency reduces cost by analyzing fewer images.  
        - **Deduplication:**  
        The pipeline compares adjacent frames using a configurable similarity threshold to remove near-duplicate images.  
        - Two comparison options are available:  
            - **Multimodal Embedding Comparison:** Uses Nova MME (Multimodal Embedding) to calculate vector distances between frames.  
            - **OpenCV ORB (Oriented FAST and Rotated BRIEF):** Compares extracted image features efficiently, with rotation invariance and speed.  
        - **Analysis Stage:**  
        Selected foundation models are applied to each frame. Users can define multiple model prompts to extract specific information.
        - **Audio Transcription:**  
        The pipeline uses Amazon Transcribe to produce timestamped subtitle segments from the video’s audio track.
        - **Output:**  
        Visual metadata and audio transcripts, both aligned with precise timestamps.

        ### Best Suited For
        - Use cases that require frame-level accuracy, such as object, action, or scene detection.  
        - Scenarios that benefit from modular extensibility, allowing additional frame-level models or extraction functions.
        ---
        ## 2. Clip-Based Customized Pipeline
        This method segments the video into short clips (shots) using OpenCV scene analysis, typically a few seconds each.

        ### Key Features
        - **Segmentation:**  
        Each detected clip is saved to Amazon S3 as an individual video segment.
        - **Analysis:**  
        - **Nova Video Understanding:** Uses prompt engineering to detect specific entities, scenes, or actions.  
        - **Nova MME Video Embeddings:** Generates clip-level embeddings and stores them in an S3-based vector database.
        - **Audio Transcription:**  
        Uses Amazon Transcribe to produce time-aligned subtitle segments.
        - **Output:**  
        Visual and audio metadata for downstream analysis and search.

        ### Best Suited For
        - Video search or shot identification tasks, such as finding clips that contain specific people, objects, or actions.  
        - Faster processing scenarios where frame-level precision is not required.

        ### Hybrid Search Benefits
        Clip-based pipelines often combine:
        - **Key-value label search** for structured accuracy.  
        - **Embedding-based search** for semantic flexibility.  
        This hybrid approach balances precision with adaptability for dynamic video retrieval.
        ---
        ## 3. Nova MME Video Embedding

        This pipeline uses the Nova MME Video Async API to:
        - Segment videos into equal-duration clips based on configuration.  
        - Generate multimodal embeddin

        5. Include the result in a <response></response> tag
        '''
    try:
        # Strands Agents SDK makes it easy to create a specialized agent
        recommendation_agent = Agent(
            system_prompt=system_prompt,
            model=nova_pro_v1,
            tools=[]  # Research-specific tools
        )

        # Call the agent and return its response
        response = recommendation_agent(query)
        return str(response)
    except Exception as e:
        return f"Error in research assistant: {str(e)}"


# Specify Bedrock LLM for the Agent
nova_lite_v1 = BedrockModel(
    model_id="amazon.nova-lite-v1:0",
)
nova_pro_v1 = BedrockModel(
    model_id="amazon.nova-pro-v1:0",
)
# System prompt
system_prompt = '''
You are a video analysis expert who advises users on the most suitable approach for analyzing videos based on their goals and input data.  
You will also help to generate request for differnet type of video processing workflows. Having conversation to request required parameters for the selected workflow. 
And confirm the values before generating the request.
'''

agent = Agent(
    tools=[generate_frame_request, get_recommendation], 
    model=nova_lite_v1,
    system_prompt=system_prompt
)


@app.entrypoint
def advisory_agent(payload):
    response = agent(json.dumps(payload))
    output = response.message['content'][0]['text']
    if "<response>" in output and "</response>" in output:
        match = re.search(r"<response>(.*?)</response>", output, re.DOTALL)
        if match:
            output = match.group(1)
    return output
    
if __name__ == "__main__":
    app.run()
    #advisory_agent({"ask":"I want to analyze an door beell IP camera recording video to find out if anyone try to steal package. what is the suitable method? "})
    #advisory_agent({"ask":"I want to index ad creative videos which are 30 seconds to 2 minutes duration and apply search efficiently to find the relevant video related to certain category such as sport, action, animation etc. And I need to customize these categories. what is the suitable method?"})