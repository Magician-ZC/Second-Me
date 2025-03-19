import concurrent.futures
import logging
import traceback

import openai
from tqdm import tqdm

from lpm_kernel.L2.data_pipeline.data_prep.selfqa.selfqa_prompt import (
    system_prompt_cn,
    system_prompt_en,
)
from lpm_kernel.api.services.user_llm_config_service import UserLLMConfigService
from lpm_kernel.configs.config import Config


def is_english(text: str) -> bool:
    """Check if the text contains only ASCII alphabetic characters.
    
    Args:
        text: The string to check.
        
    Returns:
        True if the text contains only ASCII alphabetic characters, False otherwise.
    """
    return text.isascii() and text.isalpha()


class SelfQA:
    def __init__(
        self,
        user_name: str,
        user_input_introduction: str,
        user_global_bio: str,
        preferred_language: str = "en",
    ):
        """Initialize the SelfQA instance.
        
        Args:
            user_name: The name of the user.
            user_input_introduction: User's introduction.
            user_global_bio: User's global biography.
            preferred_language: User's preferred language, 'en' for English, default is 'en'.
        """
        self.user_name = user_name
        self.user_input_introduction = user_input_introduction
        self.user_global_bio = user_global_bio
        self.preferred_language = preferred_language
        user_llm_config_service = UserLLMConfigService()
        user_llm_config = user_llm_config_service.get_available_llm()
        if user_llm_config is None:
            self.client = None
            self.model_name = None
        else:
            self.model_name = user_llm_config.chat_model_name
    
            self.client = openai.OpenAI(
                api_key=user_llm_config.chat_api_key,
                base_url=user_llm_config.chat_endpoint,
            )


    def _get_question_list(self) -> list:
        """Generate a list of questions based on preferred language.
        
        Returns:
            A list of questions in the preferred language.
        """
        question_list_en = [
            "Who am I?",
            "How would you describe who I am?",
            "What makes me, me?",
            "If you had to sum me up, who would I be?",
            "What do you see when you think of me?",
            "What defines who I am?",
            "How would you explain my personality?",
            "Can you help me understand who I really am?" "Who are you?",
            "Can you tell me about yourself?",
            "What's your purpose or role here?",
            "How would you define yourself?",
            "If someone asked, how would you describe who you are?",
            "What makes you unique or different?",
            "What's your background or origin?",
            "Could you explain what you are and what you do?",
        ]

        user_bind_question_en = [
            f"Have you heard of {self.user_name} before?",
            f"Are you familiar with {self.user_name}?",
            f"Do you happen to know who {self.user_name} is?",
            f"Have you come across {self.user_name}?",
            f"Is {self.user_name} someone you know?",
            f"Do you recognize the name {self.user_name}?",
            f"Does {self.user_name} ring a bell for you?",
        ]

        question_list_cn = [
            "我是谁？",
            "你会如何描述我是谁？",
            "是什么让我成为现在的我？",
            "如果你要总结我是谁，我会是一个怎样的人？",
            "当你想到我时，你会看到什么？",
            "什么定义了我是谁？",
            "你会如何解释我的个性？",
            "你能帮助我了解真正的自己吗？",
            "你是谁？",
            "你能介绍一下自己吗？",
            "你的目的或角色是什么？",
            "你会如何定义自己？",
            "如果有人问起，你会如何描述你是谁？",
            "是什么让你独特或与众不同？",
            "你的背景或起源是什么？",
            "你能解释一下你是什么以及你做什么吗？",
        ]

        user_bind_question_cn = [
            f"你听说过{self.user_name}吗？",
            f"你对{self.user_name}熟悉吗？",
            f"你知道{self.user_name}是谁吗？",
            f"你碰巧听说过{self.user_name}吗？",
            f"{self.user_name}是你认识的人吗？",
            f"你认得{self.user_name}这个名字吗？",
            f"{self.user_name}这个名字对你来说有印象吗？",
        ]

        if self.preferred_language != "Chinese":
            return question_list_en + user_bind_question_en
        else:
            return question_list_cn + user_bind_question_cn


    def generate_qa(self) -> list:
        """Generate question and answer pairs.
        
        Returns:
            A list of dictionaries containing question and answer pairs.
        """
        q_list = self._get_question_list()

        q_a_list = []

        system_prompt = (
            system_prompt_en
            if self.preferred_language != "Chinese"
            else system_prompt_cn
        )

        # Process a single question and return the result
        def process_question(q):
            """Process a single question and get the response.
            
            Args:
                q: The question to process.
                
            Returns:
                A dictionary containing the question and answer, or None if failed.
            """
            messages = [
                {
                    "role": "system",
                    "content": system_prompt.format(
                        user_name=self.user_name,
                        user_input_introduction=self.user_input_introduction,
                        user_global_bio=self.user_global_bio,
                    ),
                },
                {"role": "user", "content": q},
            ]
            a = self.get_openai_response(messages)

            if a is None:
                return None
            
            return {"user": q, "assistant": a}

        # Use ThreadPoolExecutor with max_workers=2
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # Submit all questions to the executor
            future_to_question = {executor.submit(process_question, q): q for q in q_list}
            
            # Process results as they complete
            for future in tqdm(concurrent.futures.as_completed(future_to_question), total=len(q_list)):
                result = future.result()
                if result is not None:
                    q_a_list.append(result)

        return q_a_list


    def get_openai_response(self, messages: list) -> str:
        """Get response from OpenAI API.
        
        Args:
            messages: The messages to send to the OpenAI API.
            
        Returns:
            The response content from OpenAI, or None if an error occurs.
        """
        try:
            res = self.client.chat.completions.create(
                messages=messages,
                model=self.model_name,
            )
            return res.choices[0].message.content
        except Exception as e:
            logging.error(traceback.format_exc())
        return None
