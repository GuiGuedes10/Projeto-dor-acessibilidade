import os
import unittest
from unittest.mock import MagicMock, patch

from test_rag import dependency, load_module


class LlmLoadingTests(unittest.TestCase):
    def setUp(self):
        self.torch = MagicMock()
        self.torch.cuda.OutOfMemoryError = type('OutOfMemoryError', (RuntimeError,), {})
        self.torch.cuda.is_available.return_value = False
        self.model = MagicMock()
        self.tokenizer = MagicMock()
        self.quantization = MagicMock()
        self.loader = load_module('llm_under_test', 'Models/llm.py', {
            'torch': self.torch,
            'dotenv': dependency('dotenv', load_dotenv=MagicMock()),
            'transformers': dependency('transformers', AutoTokenizer=self.tokenizer,
                                      AutoModelForCausalLM=self.model, BitsAndBytesConfig=self.quantization),
        })
        self.env = patch.dict(os.environ, {'MODEL_AGENTE_NAME': 'test-model'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_default_cpu_never_uses_quantization(self):
        result = self.loader.load_llm()
        self.model.from_pretrained.assert_called_once_with(
            'test-model', device_map={'': 'cpu'}, dtype=self.torch.float32)
        self.quantization.assert_not_called()
        self.assertIs(result['model'], self.model.from_pretrained.return_value)

    def test_auto_without_cuda_uses_cpu(self):
        os.environ['LLM_DEVICE'] = 'auto'
        self.loader.load_llm()
        self.assertEqual(self.model.from_pretrained.call_args.kwargs['device_map'], {'': 'cpu'})

    def test_cuda_is_explicit_and_does_not_offload(self):
        os.environ['LLM_DEVICE'] = 'cuda'
        self.torch.cuda.is_available.return_value = True
        self.loader.load_llm()
        self.assertEqual(self.model.from_pretrained.call_args.kwargs['device_map'], {'': 0})
        self.assertTrue(self.quantization.call_args.kwargs['load_in_4bit'])

    def test_unavailable_cuda_and_invalid_config_fail_clearly(self):
        for device in ['cuda', 'invalid']:
            os.environ['LLM_DEVICE'] = device
            with self.assertRaises(ValueError):
                self.loader.load_llm()
        self.model.from_pretrained.assert_not_called()

    def test_gpu_out_of_memory_has_actionable_message(self):
        os.environ['LLM_DEVICE'] = 'cuda'
        self.torch.cuda.is_available.return_value = True
        self.model.from_pretrained.side_effect = self.torch.cuda.OutOfMemoryError()
        with self.assertRaisesRegex(RuntimeError, 'LLM_DEVICE=cpu'):
            self.loader.load_llm()


if __name__ == '__main__':
    unittest.main()
