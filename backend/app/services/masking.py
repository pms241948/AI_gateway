"""PII Masking Service using Microsoft Presidio with dynamic model loading."""
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass
class PIIResult:
    """Result of PII analysis."""
    original_text: str
    masked_text: str
    entities_found: List[Dict[str, Any]]


# ============================================================================
# Built-in Recognizers (Always Available)
# ============================================================================

class KoreanRRNRecognizer(PatternRecognizer):
    """Korean Resident Registration Number (주민등록번호) recognizer."""
    
    BUILTIN_NAME = "KOREAN_RRN"
    BUILTIN_DISPLAY = "주민등록번호"
    BUILTIN_PATTERN = r"\b\d{6}-[1-4]\d{6}\b"
    
    def __init__(self):
        patterns = [
            Pattern(
                name="korean_rrn_with_dash",
                regex=r"\b\d{6}-[1-4]\d{6}\b",
                score=0.9,
            ),
            Pattern(
                name="korean_rrn_no_dash",
                regex=r"\b\d{6}[1-4]\d{6}\b",
                score=0.85,
            ),
        ]
        super().__init__(
            supported_entity="KOREAN_RRN",
            patterns=patterns,
            context=["주민등록번호", "주민번호", "resident", "rrn"],
        )


class KoreanPhoneRecognizer(PatternRecognizer):
    """Korean phone number recognizer."""
    
    BUILTIN_NAME = "KOREAN_PHONE"
    BUILTIN_DISPLAY = "한국 전화번호"
    BUILTIN_PATTERN = r"\b01[016789]-?\d{3,4}-?\d{4}\b"
    
    def __init__(self):
        patterns = [
            Pattern(
                name="korean_mobile",
                regex=r"\b01[016789]-?\d{3,4}-?\d{4}\b",
                score=0.9,
            ),
            Pattern(
                name="korean_landline",
                regex=r"\b0\d{1,2}-?\d{3,4}-?\d{4}\b",
                score=0.85,
            ),
        ]
        super().__init__(
            supported_entity="KOREAN_PHONE",
            patterns=patterns,
            context=["전화", "휴대폰", "연락처", "phone", "mobile", "tel"],
        )


# Built-in recognizer registry
BUILTIN_RECOGNIZERS = {
    "KOREAN_RRN": KoreanRRNRecognizer,
    "KOREAN_PHONE": KoreanPhoneRecognizer,
}


# ============================================================================
# PII Masking Service
# ============================================================================

class PIIMaskingService:
    """Service for detecting and masking PII in text.
    
    Supports dynamic loading of NLP models and custom recognizers.
    """
    
    # Default entities to detect (Presidio built-in + custom)
    DEFAULT_ENTITIES = [
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "CREDIT_CARD",
        "IP_ADDRESS",
        "PERSON",
        "KOREAN_RRN",
        "KOREAN_PHONE",
    ]
    
    # Default NLP models (English + Korean)
    DEFAULT_NLP_MODELS = [
        {"lang_code": "en", "model_name": "en_core_web_sm"},
        {"lang_code": "ko", "model_name": "ko_core_news_md"},
    ]
    
    # Runtime settings (can be changed dynamically)
    _runtime_enabled: bool = True
    _runtime_mask_request: bool = True
    _runtime_mask_response: bool = True
    
    # Per-language runtime settings
    _runtime_models_enabled: Dict[str, bool] = {
        "en": True,
        "ko": True,
    }
    
    def __init__(
        self,
        entities: Optional[List[str]] = None,
        mask_char: str = "*",
        mask_type: str = "replace",
        nlp_models: Optional[List[Dict[str, str]]] = None,
        custom_recognizers: Optional[List[Dict[str, Any]]] = None,
    ):
        """Initialize the PII Masking Service.
        
        Args:
            entities: List of entity types to detect
            mask_char: Character used for masking
            mask_type: Type of masking (replace, redact, hash)
            nlp_models: List of NLP models to load
            custom_recognizers: List of custom recognizer configs
        """
        self.entities = entities or self.DEFAULT_ENTITIES.copy()
        self.mask_char = mask_char
        self.mask_type = mask_type
        self._nlp_models = nlp_models or self.DEFAULT_NLP_MODELS.copy()
        self._custom_recognizers = custom_recognizers or []
        
        # Track loaded recognizers for management (must be initialized before _init_analyzer)
        self.loaded_recognizers: Dict[str, PatternRecognizer] = {}
        
        # Initialize engines
        self._init_analyzer()
        self.anonymizer = AnonymizerEngine()
    
    def _init_analyzer(self):
        """Initialize the Presidio Analyzer with configured NLP models."""
        try:
            configuration = {
                "nlp_engine_name": "spacy",
                "models": self._nlp_models,
            }
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
            self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
            
            # Add built-in Korean recognizers
            self._add_builtin_recognizers()
            
            # Add any custom recognizers
            for recognizer_config in self._custom_recognizers:
                self._add_custom_recognizer(recognizer_config)
                
        except Exception as e:
            logger.error(f"Failed to initialize PII analyzer: {e}")
            # Fallback to basic analyzer without NLP
            self.analyzer = AnalyzerEngine()
            self._add_builtin_recognizers()
    
    def _add_builtin_recognizers(self):
        """Add built-in Korean PII recognizers."""
        for name, recognizer_class in BUILTIN_RECOGNIZERS.items():
            recognizer = recognizer_class()
            self.analyzer.registry.add_recognizer(recognizer)
            self.loaded_recognizers[name] = recognizer
            
            # Add entity to detection list if not present
            if name not in self.entities:
                self.entities.append(name)
    
    def _add_custom_recognizer(self, config: Dict[str, Any]):
        """Add a custom pattern recognizer from config.
        
        Args:
            config: Dictionary with keys:
                - name: Entity type name (e.g., "KOREAN_PASSPORT")
                - pattern: Regex pattern
                - score: Confidence score (0.0-1.0)
                - context_words: Optional list of context words
        """
        try:
            name = config.get("name")
            pattern = config.get("pattern")
            score = config.get("score", 0.85)
            context_words = config.get("context_words", [])
            
            if not name or not pattern:
                logger.warning(f"Invalid recognizer config: {config}")
                return
            
            # Parse context_words if it's a JSON string
            if isinstance(context_words, str):
                try:
                    context_words = json.loads(context_words)
                except json.JSONDecodeError:
                    context_words = []
            
            recognizer = PatternRecognizer(
                supported_entity=name,
                patterns=[Pattern(name=f"{name}_pattern", regex=pattern, score=score)],
                context=context_words if context_words else None,
            )
            
            self.analyzer.registry.add_recognizer(recognizer)
            self.loaded_recognizers[name] = recognizer
            
            # Add entity to detection list
            if name not in self.entities:
                self.entities.append(name)
                
            logger.info(f"Added custom recognizer: {name}")
            
        except Exception as e:
            logger.error(f"Failed to add custom recognizer: {e}")
    
    def add_nlp_model(self, lang_code: str, model_name: str) -> bool:
        """Add a new NLP model to the engine.
        
        Note: This requires the model to be installed in the environment.
        
        Args:
            lang_code: Language code (e.g., "ko")
            model_name: spaCy model name (e.g., "ko_core_news_sm")
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if model already loaded
            for model in self._nlp_models:
                if model["lang_code"] == lang_code:
                    logger.warning(f"Model for {lang_code} already loaded")
                    return False
            
            # Add model and reinitialize
            self._nlp_models.append({"lang_code": lang_code, "model_name": model_name})
            self._init_analyzer()
            
            logger.info(f"Added NLP model: {model_name} ({lang_code})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add NLP model {model_name}: {e}")
            # Remove failed model
            self._nlp_models = [m for m in self._nlp_models if m["model_name"] != model_name]
            return False
    
    def get_loaded_models(self) -> List[Dict[str, str]]:
        """Get list of currently loaded NLP models."""
        return self._nlp_models.copy()
    
    def get_loaded_recognizers(self) -> List[str]:
        """Get list of currently loaded recognizer names."""
        return list(self.loaded_recognizers.keys())
    
    def analyze(self, text: str, language: str = "en") -> List[Dict[str, Any]]:
        """Analyze text for PII entities.
        
        Args:
            text: Text to analyze
            language: Language code (en, ko, etc.)
            
        Returns:
            List of detected PII entities with positions and types
        """
        if not text:
            return []
        
        results = self.analyzer.analyze(
            text=text,
            entities=self.entities,
            language=language,
        )
        
        return [
            {
                "entity_type": r.entity_type,
                "start": r.start,
                "end": r.end,
                "score": r.score,
                "text": text[r.start:r.end],
            }
            for r in results
        ]
    
    def mask(self, text: str, language: str = "en") -> PIIResult:
        """Mask PII in text.
        
        Args:
            text: Text to mask
            language: Language code
            
        Returns:
            PIIResult with original text, masked text, and entities found
        """
        if not text:
            return PIIResult(
                original_text=text,
                masked_text=text,
                entities_found=[],
            )
        
        # Analyze for PII
        analyzer_results = self.analyzer.analyze(
            text=text,
            entities=self.entities,
            language=language,
        )
        
        if not analyzer_results:
            return PIIResult(
                original_text=text,
                masked_text=text,
                entities_found=[],
            )
        
        # Configure anonymization operator
        if self.mask_type == "redact":
            operators = {"DEFAULT": OperatorConfig("redact")}
        elif self.mask_type == "hash":
            operators = {"DEFAULT": OperatorConfig("hash", {"hash_type": "sha256"})}
        else:  # replace
            operators = {}
            for entity in self.entities:
                operators[entity] = OperatorConfig(
                    "replace",
                    {"new_value": f"<{entity}>"},
                )
        
        # Anonymize
        anonymized = self.anonymizer.anonymize(
            text=text,
            analyzer_results=analyzer_results,
            operators=operators,
        )
        
        entities_found = [
            {
                "entity_type": r.entity_type,
                "start": r.start,
                "end": r.end,
                "score": r.score,
                "original": text[r.start:r.end],
            }
            for r in analyzer_results
        ]
        
        return PIIResult(
            original_text=text,
            masked_text=anonymized.text,
            entities_found=entities_found,
        )
    
    def mask_chat_messages(
        self,
        messages: List[Dict[str, Any]],
        language: str = "en",
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Mask PII in chat messages.
        
        Args:
            messages: List of chat messages with 'role' and 'content'
            language: Language code
            
        Returns:
            Tuple of (masked_messages, all_entities_found)
        """
        masked_messages = []
        all_entities = []
        
        for msg in messages:
            content = msg.get("content", "")
            
            if isinstance(content, str) and content:
                result = self.mask(content, language)
                masked_msg = {**msg, "content": result.masked_text}
                
                if result.entities_found:
                    all_entities.extend([
                        {**e, "message_role": msg.get("role")}
                        for e in result.entities_found
                    ])
            else:
                masked_msg = msg
            
            masked_messages.append(masked_msg)
        
        return masked_messages, all_entities
    
    def mask_response_content(
        self,
        content: str,
        language: str = "en",
    ) -> PIIResult:
        """Mask PII in LLM response content.
        
        Args:
            content: Response content text
            language: Language code
            
        Returns:
            PIIResult with masked content
        """
        return self.mask(content, language)


# ============================================================================
# Service Singleton & Factory
# ============================================================================

_masking_service: Optional[PIIMaskingService] = None


def get_masking_service() -> PIIMaskingService:
    """Get or create the PII masking service instance."""
    global _masking_service
    
    if _masking_service is None:
        _masking_service = PIIMaskingService()
    
    return _masking_service


def reload_masking_service(
    nlp_models: Optional[List[Dict[str, str]]] = None,
    custom_recognizers: Optional[List[Dict[str, Any]]] = None,
) -> PIIMaskingService:
    """Reload the masking service with new configuration.
    
    Args:
        nlp_models: List of NLP models to load
        custom_recognizers: List of custom recognizer configs
        
    Returns:
        New PIIMaskingService instance
    """
    global _masking_service
    
    _masking_service = PIIMaskingService(
        nlp_models=nlp_models,
        custom_recognizers=custom_recognizers,
    )
    
    return _masking_service


# ============================================================================
# Runtime Toggle Functions (No restart required)
# ============================================================================

def set_pii_enabled(enabled: bool) -> None:
    """Enable or disable PII masking at runtime."""
    PIIMaskingService._runtime_enabled = enabled
    logger.info(f"PII masking {'enabled' if enabled else 'disabled'}")


def set_mask_request(enabled: bool) -> None:
    """Enable or disable request masking at runtime."""
    PIIMaskingService._runtime_mask_request = enabled
    logger.info(f"Request masking {'enabled' if enabled else 'disabled'}")


def set_mask_response(enabled: bool) -> None:
    """Enable or disable response masking at runtime."""
    PIIMaskingService._runtime_mask_response = enabled
    logger.info(f"Response masking {'enabled' if enabled else 'disabled'}")


def get_runtime_settings() -> Dict[str, bool]:
    """Get current runtime PII settings."""
    return {
        "enabled": PIIMaskingService._runtime_enabled,
        "mask_request": PIIMaskingService._runtime_mask_request,
        "mask_response": PIIMaskingService._runtime_mask_response,
    }


def is_pii_enabled() -> bool:
    """Check if PII masking is currently enabled."""
    return PIIMaskingService._runtime_enabled


def should_mask_request() -> bool:
    """Check if request masking is enabled."""
    return PIIMaskingService._runtime_enabled and PIIMaskingService._runtime_mask_request


def should_mask_response() -> bool:
    """Check if response masking is enabled."""
    return PIIMaskingService._runtime_enabled and PIIMaskingService._runtime_mask_response


# ============================================================================
# Per-Language Model Toggle Functions
# ============================================================================

def set_model_enabled(lang_code: str, enabled: bool) -> None:
    """Enable or disable a specific language model at runtime."""
    PIIMaskingService._runtime_models_enabled[lang_code] = enabled
    logger.info(f"NLP model '{lang_code}' {'enabled' if enabled else 'disabled'}")


def get_model_enabled(lang_code: str) -> bool:
    """Check if a specific language model is enabled."""
    return PIIMaskingService._runtime_models_enabled.get(lang_code, False)


def get_all_models_status() -> Dict[str, bool]:
    """Get enabled status of all language models."""
    return PIIMaskingService._runtime_models_enabled.copy()


def get_enabled_languages() -> List[str]:
    """Get list of enabled language codes."""
    return [lang for lang, enabled in PIIMaskingService._runtime_models_enabled.items() if enabled]
