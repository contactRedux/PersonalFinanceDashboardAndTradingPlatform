# ADR-008 — PyTorch for LSTM Price Prediction Model

**Date:** 2025-03-15  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

The ML prediction feature requires an LSTM (Long Short-Term Memory) neural network that takes
a window of OHLCV feature vectors and outputs 3-class return-direction probabilities (down,
flat, up). Both PyTorch and TensorFlow/Keras are mature, production-capable deep learning
frameworks with strong LSTM support. The choice between them is primarily one of developer
ergonomics, ecosystem fit, and deployment footprint rather than capability.

TensorFlow/Keras offers a high-level `tf.keras.layers.LSTM` API that is approachable for
practitioners new to deep learning, along with TensorFlow Serving for production model serving.
However, its eager/graph execution duality (particularly in TF 1.x/2.x transition codebases),
larger Docker image footprint (~1.5 GB), and relative complexity of custom training loops make
it less suitable for a codebase where ML is one of several features rather than the primary
product. TensorFlow Lite is a separate deployment target that would require model conversion.

PyTorch has become the dominant framework in academic ML research and is increasingly the
default for new production systems. Its eager execution model means Python debugging tools
(pdb, print statements, standard exceptions) work naturally during model development.
`torch.nn.LSTM` and the surrounding module ecosystem are idiomatic Python classes.

## Decision

Use **PyTorch** for the LSTM price prediction model implementation.

The `LSTMPricePredictor` class (`ml/models/lstm/model.py`) inherits from `torch.nn.Module`
and uses `torch.nn.LSTM` for the sequence encoder with a linear classification head. Training
is dispatched as a Celery task and weights are saved as `.pt` checkpoint files in
`/app/data/ml_weights/lstm/`. Inference is performed by loading the checkpoint with
`torch.load()` in the `GET /ml/lstm/predict` endpoint. The same PyTorch installation serves
the deferred Transformer model when it is implemented (see ADR-005).

## Consequences

### Positive
- Pythonic, imperative API: custom training loops use standard Python control flow; debugging
  requires no framework-specific tools
- Strong research ecosystem: most financial ML papers publish PyTorch reference implementations,
  making it easy to incorporate new architectures
- `torch.nn.TransformerEncoder` is available in the same package (see ADR-005), so no new
  dependency is needed when the Transformer is implemented
- Active community and extensive documentation; StackOverflow coverage is excellent

### Negative
- PyTorch CPU-only wheel is ~250 MB; the GPU wheel is ~2 GB — this is the largest single
  dependency in the backend Docker image
- PyTorch does not have a built-in serving framework comparable to TensorFlow Serving;
  production serving relies on in-process `torch.load()` + inference, which is acceptable at
  current scale but may need to be replaced with TorchServe for high-throughput inference
- Saving/loading models with `torch.load(..., weights_only=False)` carries a security caveat
  (arbitrary code execution from malicious pickle files); model files must be treated as trusted
  artefacts and not accepted from external sources

### Neutral
- Model weights are stored as PyTorch `.pt` checkpoint dictionaries containing `state_dict`,
  `n_features`, `hidden_size`, `seq_len`, `mean`, and `std` normalisation parameters
- The CPU-only PyTorch build is used in the current Docker image; switching to GPU requires
  changing the base image and Celery worker configuration (see ADR-005 re-engagement criteria)
