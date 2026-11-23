"""Carregamento explícito da LLM: CPU por padrão; CUDA de 4 bits opcional."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
logger = logging.getLogger(__name__)


def load_llm():
    model_name = os.getenv('MODEL_AGENTE_NAME', '').strip()
    if not model_name:
        raise ValueError('Defina MODEL_AGENTE_NAME no arquivo .env do backend.')
    device = os.getenv('LLM_DEVICE', 'cpu').strip().lower()
    if device not in {'cpu', 'cuda', 'auto'}:
        raise ValueError('LLM_DEVICE deve ser cpu, cuda ou auto.')
    if device == 'auto':
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if device == 'cuda' and not torch.cuda.is_available():
        raise ValueError('CUDA não está disponível. Use LLM_DEVICE=cpu no .env.')

    if device == 'cpu':
        # Sem bitsandbytes e sem despacho automático para GPU/disco.
        options = {'device_map': {'': 'cpu'}, 'dtype': torch.float32}
    else:
        options = {
            'device_map': {'': 0},
            'quantization_config': BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type='nf4',
                bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True,
            ),
        }
    logger.info('Carregando modelo %s em %s', model_name, device)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    try:
        model = AutoModelForCausalLM.from_pretrained(model_name, **options)
    except torch.cuda.OutOfMemoryError as error:
        raise RuntimeError('Memória de GPU insuficiente. Use LLM_DEVICE=cpu ou um modelo menor.') from error
    model.eval()
    return {'model': model, 'tokenizer': tokenizer}
