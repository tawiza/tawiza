"""
Ollama Inference Service - Implementation of IModelInference port.
"""

from collections.abc import Callable
from typing import Any

from loguru import logger

from src.application.ports.ml_ports import IModelInference
from src.infrastructure.ml.ollama.ollama_adapter import OllamaAdapter
from src.infrastructure.prompts import PromptManager, get_prompt_manager


class OllamaInferenceService(IModelInference):
    """
    Implementation of model inference using Ollama.

    This service provides LLM inference using locally running Ollama models.
    """

    def __init__(
        self,
        ollama_adapter: OllamaAdapter,
        default_model: str = "qwen3.5:27b",
        use_prompt_templates: bool = True,
        prompt_manager: PromptManager | None = None,
    ):
        """
        Initialize Ollama inference service.

        Args:
            ollama_adapter: Ollama adapter instance
            default_model: Default model to use if not specified
            use_prompt_templates: Enable prompt template usage
            prompt_manager: Optional PromptManager instance (uses singleton if None)
        """
        self.ollama = ollama_adapter
        self.default_model = default_model
        self.use_prompt_templates = use_prompt_templates

        # Initialize prompt manager if enabled
        if self.use_prompt_templates:
            self.prompt_manager = prompt_manager or get_prompt_manager()
            logger.info("PromptManager enabled for Ollama inference")
        else:
            self.prompt_manager = None

        # Map model_id to Ollama model names
        # In production, this would be fetched from database
        self._model_mapping: dict[str, str] = {}

    def register_model(self, model_id: str, ollama_model_name: str) -> None:
        """
        Register a model ID to Ollama model name mapping.

        Args:
            model_id: Model UUID or identifier
            ollama_model_name: Ollama model name (e.g., "qwen3.5:27b")
        """
        self._model_mapping[model_id] = ollama_model_name
        logger.info(f"Registered model {model_id} -> {ollama_model_name}")

    def _get_ollama_model(self, model_id: str) -> str:
        """
        Get Ollama model name for a given model ID.

        Args:
            model_id: Model identifier

        Returns:
            Ollama model name
        """
        # Try to find in mapping
        if model_id in self._model_mapping:
            return self._model_mapping[model_id]

        # Try using model_id directly (might be Ollama model name)
        return model_id if ":" in model_id else self.default_model

    async def predict(
        self,
        model_id: str,
        input_data: dict[str, Any],
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run inference on a model.

        Args:
            model_id: Model identifier or Ollama model name
            input_data: Input data - expects {"prompt": "..."} or {"messages": [...]}
            parameters: Optional parameters (temperature, max_tokens, top_p, etc.)

        Returns:
            Prediction output with text, confidence, usage stats
        """
        try:
            # Get Ollama model name
            ollama_model = self._get_ollama_model(model_id)

            # Extract parameters
            params = parameters or {}
            temperature = params.get("temperature", 0.7)
            max_tokens = params.get("max_tokens", 512)

            logger.info(
                f"Running inference with model {ollama_model} "
                f"(temp={temperature}, max_tokens={max_tokens})"
            )

            # Check if chat or completion
            if "messages" in input_data:
                # Chat completion
                response = await self.ollama.chat(
                    model=ollama_model,
                    messages=input_data["messages"],
                    temperature=temperature,
                    stream=False,
                )

                # Extract response
                output_text = response.get("message", {}).get("content", "")

            elif "prompt" in input_data:
                # Text completion
                response = await self.ollama.generate(
                    model=ollama_model,
                    prompt=input_data["prompt"],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False,
                )

                # Extract response
                output_text = response.get("response", "")

            else:
                raise ValueError("Input data must contain either 'prompt' or 'messages'")

            # Calculate confidence (mock for now - could use logprobs if available)
            confidence = 0.85  # Placeholder

            # Extract usage stats
            usage = {
                "prompt_tokens": response.get("prompt_eval_count", 0),
                "completion_tokens": response.get("eval_count", 0),
                "total_tokens": (
                    response.get("prompt_eval_count", 0) + response.get("eval_count", 0)
                ),
            }

            result = {
                "text": output_text,
                "confidence": confidence,
                "usage": usage,
                "model": ollama_model,
                "raw_response": response,
            }

            logger.info(f"Inference completed. Generated {usage['completion_tokens']} tokens")

            return result

        except Exception as e:
            logger.error(f"Inference failed: {e}")
            raise

    async def predict_with_template(
        self,
        model_id: str,
        template_name: str,
        template_variables: dict[str, Any],
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run inference using a prompt template.

        Args:
            model_id: Model identifier or Ollama model name
            template_name: Name of the prompt template to use
            template_variables: Variables to render the template with
            parameters: Optional parameters (temperature, max_tokens, top_p, etc.)

        Returns:
            Prediction output with text, confidence, usage stats

        Raises:
            ValueError: If template not found or prompt manager not enabled
        """
        if not self.use_prompt_templates or self.prompt_manager is None:
            raise ValueError(
                "Prompt templates are not enabled. Set use_prompt_templates=True in constructor."
            )

        try:
            # Render the template
            prompt = self.prompt_manager.render(template_name, **template_variables)

            logger.info(
                f"Running inference with template '{template_name}' "
                f"(variables: {list(template_variables.keys())})"
            )

            # Run inference with the rendered prompt
            input_data = {"prompt": prompt}
            result = await self.predict(
                model_id=model_id, input_data=input_data, parameters=parameters
            )

            # Add template info to result
            result["template_used"] = template_name
            result["template_variables"] = template_variables

            return result

        except ValueError as e:
            logger.error(f"Template rendering failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Template-based inference failed: {e}")
            raise

    def _build_prompt_from_task(
        self, task_type: str, input_text: str, additional_context: dict[str, Any] | None = None
    ) -> str:
        """
        Build a prompt for a specific task type using templates if available.

        Args:
            task_type: Type of task (classification, ner, summarization, etc.)
            input_text: Input text to process
            additional_context: Additional context for the template

        Returns:
            Formatted prompt string
        """
        if not self.use_prompt_templates or self.prompt_manager is None:
            # Fallback to simple prompt
            return f"Task: {task_type}\n\nInput: {input_text}"

        # Map task types to template names
        template_mapping = {
            "classification": "text_classification",
            "ner": "named_entity_recognition",
            "summarization": "text_summarization",
            "chat": "chat_simple",
        }

        template_name = template_mapping.get(task_type)

        if template_name and self.prompt_manager.get_template(template_name):
            try:
                # Prepare variables
                variables = {"text": input_text}
                if additional_context:
                    variables.update(additional_context)

                # Render template
                return self.prompt_manager.render(template_name, **variables)
            except (ValueError, KeyError) as e:
                logger.warning(
                    f"Failed to use template '{template_name}': {e}, falling back to simple prompt"
                )

        # Fallback
        return f"Task: {task_type}\n\nInput: {input_text}"

    async def classify_text(
        self, model_id: str, text: str, categories: str, parameters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Classify text into categories using a prompt template.

        Args:
            model_id: Model identifier
            text: Text to classify
            categories: Comma-separated list of categories
            parameters: Optional parameters

        Returns:
            Classification result
        """
        if self.use_prompt_templates and self.prompt_manager:
            try:
                return await self.predict_with_template(
                    model_id=model_id,
                    template_name="text_classification",
                    template_variables={"text": text, "categories": categories},
                    parameters=parameters,
                )
            except ValueError:
                # Template not found, fall back to direct inference
                pass

        # Fallback: direct inference
        prompt = f"Classify the following text into one of these categories: {categories}\n\nText: {text}\n\nCategory:"
        return await self.predict(
            model_id=model_id, input_data={"prompt": prompt}, parameters=parameters
        )

    async def extract_entities(
        self, model_id: str, text: str, parameters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Extract named entities from text using a prompt template.

        Args:
            model_id: Model identifier
            text: Text to analyze
            parameters: Optional parameters

        Returns:
            Entity extraction result
        """
        if self.use_prompt_templates and self.prompt_manager:
            try:
                return await self.predict_with_template(
                    model_id=model_id,
                    template_name="named_entity_recognition",
                    template_variables={"text": text},
                    parameters=parameters,
                )
            except ValueError as e:
                logger.debug(f"Template 'named_entity_recognition' not found, using fallback: {e}")

        # Fallback
        prompt = f"Extract named entities from the following text. Return entities in JSON format with their types.\n\nText: {text}\n\nEntities:"
        return await self.predict(
            model_id=model_id, input_data={"prompt": prompt}, parameters=parameters
        )

    async def summarize_text(
        self,
        model_id: str,
        text: str,
        max_words: int = 100,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Summarize text using a prompt template.

        Args:
            model_id: Model identifier
            text: Text to summarize
            max_words: Maximum words in summary
            parameters: Optional parameters

        Returns:
            Summarization result
        """
        if self.use_prompt_templates and self.prompt_manager:
            try:
                return await self.predict_with_template(
                    model_id=model_id,
                    template_name="text_summarization",
                    template_variables={"text": text, "max_words": str(max_words)},
                    parameters=parameters,
                )
            except ValueError as e:
                logger.debug(f"Template 'text_summarization' not found, using fallback: {e}")

        # Fallback
        prompt = f"Please summarize the following text in {max_words} words or less:\n\n{text}\n\nSummary:"
        return await self.predict(
            model_id=model_id, input_data={"prompt": prompt}, parameters=parameters
        )

    async def analyze_sentiment(
        self, model_id: str, text: str, parameters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Analyze sentiment of text using a prompt template.

        Args:
            model_id: Model identifier
            text: Text to analyze
            parameters: Optional parameters

        Returns:
            Sentiment analysis result with sentiment, confidence, and key phrases
        """
        if self.use_prompt_templates and self.prompt_manager:
            try:
                return await self.predict_with_template(
                    model_id=model_id,
                    template_name="sentiment_analysis",
                    template_variables={"text": text},
                    parameters=parameters,
                )
            except ValueError as e:
                logger.debug(f"Template 'sentiment_analysis' not found, using fallback: {e}")

        # Fallback
        prompt = f"Analyze the sentiment of the following text. Return: sentiment (positive/negative/neutral), confidence score, and key phrases.\n\nText: {text}\n\nAnalysis:"
        return await self.predict(
            model_id=model_id, input_data={"prompt": prompt}, parameters=parameters
        )

    async def answer_question(
        self, model_id: str, question: str, context: str, parameters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Answer a question based on provided context using a prompt template.

        Args:
            model_id: Model identifier
            question: Question to answer
            context: Context to use for answering
            parameters: Optional parameters

        Returns:
            Question answering result
        """
        if self.use_prompt_templates and self.prompt_manager:
            try:
                return await self.predict_with_template(
                    model_id=model_id,
                    template_name="question_answering",
                    template_variables={"question": question, "context": context},
                    parameters=parameters,
                )
            except ValueError as e:
                logger.debug(f"Template 'question_answering' not found, using fallback: {e}")

        # Fallback
        prompt = f"Answer the following question based on the given context. If the answer is not in the context, say 'I don't know'.\n\nContext: {context}\n\nQuestion: {question}\n\nAnswer:"
        return await self.predict(
            model_id=model_id, input_data={"prompt": prompt}, parameters=parameters
        )

    async def translate_text(
        self,
        model_id: str,
        text: str,
        source_lang: str,
        target_lang: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Translate text from source language to target language using a prompt template.

        Args:
            model_id: Model identifier
            text: Text to translate
            source_lang: Source language (e.g., "English", "French")
            target_lang: Target language
            parameters: Optional parameters

        Returns:
            Translation result
        """
        if self.use_prompt_templates and self.prompt_manager:
            try:
                return await self.predict_with_template(
                    model_id=model_id,
                    template_name="translation",
                    template_variables={
                        "text": text,
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                    },
                    parameters=parameters,
                )
            except ValueError as e:
                logger.debug(f"Template 'translation' not found, using fallback: {e}")

        # Fallback
        prompt = f"Translate the following text from {source_lang} to {target_lang}:\n\n{text}\n\nTranslation:"
        return await self.predict(
            model_id=model_id, input_data={"prompt": prompt}, parameters=parameters
        )

    async def review_code(
        self, model_id: str, code: str, language: str, parameters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Review code for bugs, security issues, and best practices using a prompt template.

        Args:
            model_id: Model identifier
            code: Code to review
            language: Programming language
            parameters: Optional parameters

        Returns:
            Code review result with bugs, security issues, and suggestions
        """
        if self.use_prompt_templates and self.prompt_manager:
            try:
                return await self.predict_with_template(
                    model_id=model_id,
                    template_name="code_review",
                    template_variables={"code": code, "language": language},
                    parameters=parameters,
                )
            except ValueError as e:
                logger.debug(f"Template 'code_review' not found, using fallback: {e}")

        # Fallback
        prompt = f"Review the following {language} code for bugs, security issues, performance problems, and best practices violations:\n\n```{language}\n{code}\n```\n\nReview:"
        return await self.predict(
            model_id=model_id, input_data={"prompt": prompt}, parameters=parameters
        )

    async def analyze_error(
        self,
        model_id: str,
        error_type: str,
        error_message: str,
        stack_trace: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze an error and provide solutions using a prompt template.

        Args:
            model_id: Model identifier
            error_type: Type of error (e.g., "ValueError", "TypeError")
            error_message: Error message
            stack_trace: Stack trace
            parameters: Optional parameters

        Returns:
            Error analysis with root cause and solutions
        """
        if self.use_prompt_templates and self.prompt_manager:
            try:
                return await self.predict_with_template(
                    model_id=model_id,
                    template_name="error_analysis",
                    template_variables={
                        "error_type": error_type,
                        "error_message": error_message,
                        "stack_trace": stack_trace,
                    },
                    parameters=parameters,
                )
            except ValueError as e:
                logger.debug(f"Template 'error_analysis' not found, using fallback: {e}")

        # Fallback
        prompt = f"Analyze this error and provide root cause, why it happened, how to fix it, and how to prevent it:\n\nError: {error_type}\nMessage: {error_message}\nStack trace: {stack_trace}\n\nAnalysis:"
        return await self.predict(
            model_id=model_id, input_data={"prompt": prompt}, parameters=parameters
        )

    async def health_check(self, model_id: str) -> bool:
        """
        Check if a model is healthy and ready.

        Args:
            model_id: Model identifier

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check Ollama service health
            is_healthy = await self.ollama.health_check()
            if not is_healthy:
                return False

            # Check if model exists
            ollama_model = self._get_ollama_model(model_id)
            models = await self.ollama.list_models()
            model_names = [m["name"] for m in models]

            return ollama_model in model_names

        except Exception as e:
            logger.error(f"Health check failed for model {model_id}: {e}")
            return False

    async def get_model_info(self, model_id: str) -> dict[str, Any]:
        """
        Get information about a deployed model.

        Args:
            model_id: Model identifier

        Returns:
            Model information
        """
        try:
            ollama_model = self._get_ollama_model(model_id)

            # Get model info from Ollama
            info = await self.ollama.get_model_info(ollama_model)

            return {
                "model_id": model_id,
                "ollama_model": ollama_model,
                "details": info.get("details", {}),
                "parameters": info.get("parameters", {}),
                "template": info.get("template", ""),
                "license": info.get("license", ""),
            }

        except Exception as e:
            logger.error(f"Failed to get model info for {model_id}: {e}")
            raise


class OllamaTrainingService:
    """
    Service for training/fine-tuning with Ollama.

    This handles QLoRA fine-tuning and model customization.
    """

    def __init__(self, ollama_adapter: OllamaAdapter):
        """
        Initialize training service.

        Args:
            ollama_adapter: Ollama adapter instance
        """
        self.ollama = ollama_adapter

    async def create_custom_model(
        self,
        model_name: str,
        base_model: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """
        Create a custom Ollama model from a Modelfile.

        Args:
            model_name: Name for the new model
            base_model: Base model to use (e.g., "qwen3.5:27b")
            system_prompt: Optional system prompt to bake in
            temperature: Optional default temperature

        Returns:
            Model name
        """
        # Build Modelfile
        modelfile_parts = [f"FROM {base_model}"]

        if system_prompt:
            modelfile_parts.append(f"SYSTEM {system_prompt}")

        if temperature is not None:
            modelfile_parts.append(f"PARAMETER temperature {temperature}")

        modelfile = "\n".join(modelfile_parts)

        logger.info(f"Creating custom model {model_name} from {base_model}")

        # Create model
        await self.ollama.create_model(name=model_name, modelfile=modelfile)

        logger.info(f"Successfully created model {model_name}")

        return model_name

    async def prepare_training_data(
        self, annotations: list, output_path: str, task_type: str = "classification"
    ) -> str:
        """
        Prepare training data from Label Studio annotations.

        Args:
            annotations: Annotations from Label Studio
            output_path: Path to save training data
            task_type: Type of task (classification, ner, etc.)

        Returns:
            Path to prepared data
        """
        from pathlib import Path

        data_path = await self.ollama.prepare_finetuning_data(
            annotations=annotations, output_path=Path(output_path), task_type=task_type
        )

        logger.info(f"Prepared training data at {data_path}")

        return str(data_path)

    async def fine_tune_with_qlora(
        self,
        base_model: str,
        training_data_path: str,
        output_model_name: str,
        epochs: int = 3,
        batch_size: int = 4,
        learning_rate: float = 2e-4,
        lora_r: int = 16,
        lora_alpha: int = 32,
        max_seq_length: int = 2048,
        progress_callback: Callable | None = None,
    ) -> dict[str, Any]:
        """
        Fine-tune a model using QLoRA (Quantized LoRA).

        Uses LoRAFineTuner with Unsloth for efficient training:
        - 2x faster training vs standard LoRA
        - 70% less VRAM usage
        - MLflow experiment tracking

        Requirements:
            pip install unsloth transformers trl datasets torch

        Args:
            base_model: Base model name (HuggingFace format)
            training_data_path: Path to training data (JSONL)
            output_model_name: Name for fine-tuned model
            epochs: Number of epochs
            batch_size: Batch size per device
            learning_rate: Learning rate
            lora_r: LoRA rank (16, 32, 64)
            lora_alpha: LoRA scaling (typically 2*r)
            max_seq_length: Maximum sequence length
            progress_callback: Optional progress callback

        Returns:
            dict: Training results with metrics
        """
        from pathlib import Path

        result = await self.ollama.finetune_with_qlora(
            base_model=base_model,
            training_data_path=Path(training_data_path),
            output_model_name=output_model_name,
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            lora_r=lora_r,
            lora_alpha=lora_alpha,
            max_seq_length=max_seq_length,
            progress_callback=progress_callback,
        )

        return result
