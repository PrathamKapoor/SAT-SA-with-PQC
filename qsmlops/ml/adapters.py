"""ML Framework Adapter Layer.
Provides unified interfaces for sklearn, PyTorch, and TensorFlow models.
"""
from __future__ import annotations

import json
import pickle
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None

try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    tf = None

try:
    import sklearn
    from sklearn.base import BaseEstimator
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    BaseEstimator = object


@dataclass
class ModelMetadata:
    framework: str
    model_type: str
    input_shape: tuple
    output_shape: tuple
    parameters: int
    training_time: float
    hyperparameters: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    version: str = "1.0.0"


@dataclass
class TrainingResult:
    model: Any
    metadata: ModelMetadata
    metrics: dict
    artifacts: dict


class TrainerInterface(ABC):
    @abstractmethod
    def train(self, X_train, y_train, X_val=None, y_val=None, **kwargs) -> TrainingResult:
        pass

    @abstractmethod
    def evaluate(self, model, X_test, y_test) -> dict:
        pass

    @abstractmethod
    def serialize(self, model, path: Path) -> str:
        pass

    @abstractmethod
    def deserialize(self, path: Path) -> Any:
        pass

    @abstractmethod
    def get_metadata(self, model) -> ModelMetadata:
        pass


class ArtifactSerializerInterface(ABC):
    @abstractmethod
    def serialize(self, obj: Any) -> bytes:
        pass

    @abstractmethod
    def deserialize(self, data: bytes) -> Any:
        pass

    @abstractmethod
    def get_digest(self, obj: Any) -> str:
        pass


class SKLearnTrainer(TrainerInterface):
    def __init__(self, estimator_class, **estimator_kwargs):
        self.estimator_class = estimator_class
        self.estimator_kwargs = estimator_kwargs

    def train(self, X_train, y_train, X_val=None, y_val=None, **kwargs) -> TrainingResult:
        start = time.time()
        model = self.estimator_class(**self.estimator_kwargs)
        model.fit(X_train, y_train)
        training_time = time.time() - start

        metrics = {}
        if X_val is not None and y_val is not None:
            metrics = self.evaluate(model, X_val, y_val)

        metadata = ModelMetadata(
            framework="sklearn",
            model_type=self.estimator_class.__name__,
            input_shape=X_train.shape[1:],
            output_shape=(1,) if y_train.ndim == 1 else y_train.shape[1:],
            parameters=self._count_parameters(model),
            training_time=training_time,
            hyperparameters=self.estimator_kwargs,
            metrics=metrics,
        )

        return TrainingResult(
            model=model,
            metadata=metadata,
            metrics=metrics,
            artifacts={}
        )

    def evaluate(self, model, X_test, y_test) -> dict:
        from sklearn.metrics import mean_squared_error, r2_score, accuracy_score, f1_score
        
        y_pred = model.predict(X_test)
        metrics = {}
        
        if hasattr(model, 'predict_proba'):
            metrics['accuracy'] = accuracy_score(y_test, y_pred)
            metrics['f1'] = f1_score(y_test, y_pred, average='weighted')
        else:
            metrics['mse'] = mean_squared_error(y_test, y_pred)
            metrics['r2'] = r2_score(y_test, y_pred)
        
        return metrics

    def serialize(self, model, path: Path) -> str:
        path.write_bytes(pickle.dumps(model))
        return str(path)

    def deserialize(self, path: Path) -> Any:
        return pickle.loads(path.read_bytes())

    def get_metadata(self, model) -> ModelMetadata:
        return ModelMetadata(
            framework="sklearn",
            model_type=model.__class__.__name__,
            input_shape=getattr(model, 'n_features_in_', (0,)),
            output_shape=(1,),
            parameters=self._count_parameters(model),
            training_time=0.0,
        )

    def _count_parameters(self, model) -> int:
        if hasattr(model, 'coef_'):
            return model.coef_.size + (model.intercept_.size if hasattr(model, 'intercept_') else 0)
        if hasattr(model, 'feature_importances_'):
            return len(model.feature_importances_)
        return 0


class SKLearnSerializer(ArtifactSerializerInterface):
    def serialize(self, obj: Any) -> bytes:
        return pickle.dumps(obj)

    def deserialize(self, data: bytes) -> Any:
        return pickle.loads(data)

    def get_digest(self, obj: Any) -> str:
        import hashlib
        return hashlib.sha3_256(self._canonical_bytes(obj)).hexdigest()

    @staticmethod
    def _canonical_bytes(obj: Any) -> bytes:
        return pickle.dumps(_canonicalize(obj), protocol=pickle.HIGHEST_PROTOCOL)


def _canonicalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _canonicalize(v) for k, v in sorted(obj.items(), key=lambda kv: repr(kv[0]))}
    if isinstance(obj, (set, frozenset)):
        return tuple(sorted((_canonicalize(v) for v in obj), key=repr))
    if isinstance(obj, (list, tuple)):
        return tuple(_canonicalize(v) for v in obj)
    if isinstance(obj, np.ndarray):
        return obj.tobytes()
    return obj


if TORCH_AVAILABLE:
    class PyTorchTrainer(TrainerInterface):
        def __init__(self, model_class, optimizer_class=torch.optim.Adam, 
                     loss_fn=nn.MSELoss(), **model_kwargs):
            self.model_class = model_class
            self.optimizer_class = optimizer_class
            self.loss_fn = loss_fn
            self.model_kwargs = model_kwargs

        def train(self, X_train, y_train, X_val=None, y_val=None, 
                  epochs=100, batch_size=32, lr=0.001, **kwargs) -> TrainingResult:
            start = time.time()
            
            model = self.model_class(**self.model_kwargs)
            optimizer = self.optimizer_class(model.parameters(), lr=lr)
            
            X_tensor = torch.FloatTensor(X_train)
            y_tensor = torch.FloatTensor(y_train).reshape(-1, 1)
            
            dataset = torch.utils.data.TensorDataset(X_tensor, y_tensor)
            loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)
            
            model.train()
            for epoch in range(epochs):
                for batch_X, batch_y in loader:
                    optimizer.zero_grad()
                    pred = model(batch_X)
                    loss = self.loss_fn(pred, batch_y)
                    loss.backward()
                    optimizer.step()
            
            training_time = time.time() - start
            
            metrics = {}
            if X_val is not None and y_val is not None:
                metrics = self.evaluate(model, X_val, y_val)
            
            metadata = ModelMetadata(
                framework="pytorch",
                model_type=self.model_class.__name__,
                input_shape=X_train.shape[1:],
                output_shape=(1,),
                parameters=sum(p.numel() for p in model.parameters()),
                training_time=training_time,
                hyperparameters={"epochs": epochs, "batch_size": batch_size, "lr": lr, **self.model_kwargs},
                metrics=metrics,
            )
            
            return TrainingResult(model=model, metadata=metadata, metrics=metrics, artifacts={})

        def evaluate(self, model, X_test, y_test) -> dict:
            model.eval()
            with torch.no_grad():
                X_tensor = torch.FloatTensor(X_test)
                y_tensor = torch.FloatTensor(y_test).reshape(-1, 1)
                pred = model(X_tensor)
                loss = self.loss_fn(pred, y_tensor)
                return {'loss': loss.item(), 'mse': loss.item()}

        def serialize(self, model, path: Path) -> str:
            torch.save(model.state_dict(), path)
            return str(path)

        def deserialize(self, path: Path) -> Any:
            model = self.model_class(**self.model_kwargs)
            model.load_state_dict(torch.load(path))
            model.eval()
            return model

        def get_metadata(self, model) -> ModelMetadata:
            return ModelMetadata(
                framework="pytorch",
                model_type=model.__class__.__name__,
                input_shape=tuple(model.parameters())[0].shape if list(model.parameters()) else (0,),
                output_shape=(1,),
                parameters=sum(p.numel() for p in model.parameters()),
                training_time=0.0,
            )

    class PyTorchSerializer(ArtifactSerializerInterface):
        def serialize(self, obj: Any) -> bytes:
            import io
            buffer = io.BytesIO()
            torch.save(obj.state_dict(), buffer)
            return buffer.getvalue()

        def deserialize(self, data: bytes) -> Any:
            import io
            buffer = io.BytesIO(data)
            return torch.load(buffer)

        def get_digest(self, obj: Any) -> str:
            import hashlib
            return hashlib.sha3_256(self.serialize(obj)).hexdigest()


if TF_AVAILABLE:
    class TensorFlowTrainer(TrainerInterface):
        def __init__(self, model_builder, optimizer='adam', loss='mse', **model_kwargs):
            self.model_builder = model_builder
            self.optimizer = optimizer
            self.loss = loss
            self.model_kwargs = model_kwargs

        def train(self, X_train, y_train, X_val=None, y_val=None,
                  epochs=100, batch_size=32, **kwargs) -> TrainingResult:
            start = time.time()
            
            model = self.model_builder(**self.model_kwargs)
            model.compile(optimizer=self.optimizer, loss=self.loss)
            
            history = model.fit(
                X_train, y_train,
                epochs=epochs,
                batch_size=batch_size,
                validation_data=(X_val, y_val) if X_val is not None else None,
                verbose=0
            )
            
            training_time = time.time() - start
            
            metrics = {}
            if X_val is not None and y_val is not None:
                metrics = self.evaluate(model, X_val, y_val)
            
            metadata = ModelMetadata(
                framework="tensorflow",
                model_type=model.__class__.__name__,
                input_shape=X_train.shape[1:],
                output_shape=y_train.shape[1:],
                parameters=model.count_params(),
                training_time=training_time,
                hyperparameters={"epochs": epochs, "batch_size": batch_size, **self.model_kwargs},
                metrics=metrics,
            )
            
            return TrainingResult(model=model, metadata=metadata, metrics=metrics, artifacts={})

        def evaluate(self, model, X_test, y_test) -> dict:
            results = model.evaluate(X_test, y_test, verbose=0, return_dict=True)
            return results

        def serialize(self, model, path: Path) -> str:
            model.save(path)
            return str(path)

        def deserialize(self, path: Path) -> Any:
            return tf.keras.models.load_model(path)

        def get_metadata(self, model) -> ModelMetadata:
            return ModelMetadata(
                framework="tensorflow",
                model_type=model.__class__.__name__,
                input_shape=model.input_shape[1:] if model.input_shape else (0,),
                output_shape=model.output_shape[1:] if model.output_shape else (0,),
                parameters=model.count_params(),
                training_time=0.0,
            )

    class TensorFlowSerializer(ArtifactSerializerInterface):
        def serialize(self, obj: Any) -> bytes:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                path = Path(tmpdir) / "model"
                obj.save(path)
                return (path / "saved_model.pb").read_bytes()

        def deserialize(self, data: bytes) -> Any:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                path = Path(tmpdir) / "model"
                path.mkdir()
                (path / "saved_model.pb").write_bytes(data)
                return tf.keras.models.load_model(path)

        def get_digest(self, obj: Any) -> str:
            import hashlib
            return hashlib.sha3_256(self.serialize(obj)).hexdigest()


def get_trainer(framework: str, **kwargs) -> TrainerInterface:
    framework = framework.lower()
    if framework == "sklearn":
        return SKLearnTrainer(**kwargs)
    elif framework == "pytorch":
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not installed")
        return PyTorchTrainer(**kwargs)
    elif framework in ("tensorflow", "tf", "keras"):
        if not TF_AVAILABLE:
            raise RuntimeError("TensorFlow not installed")
        return TensorFlowTrainer(**kwargs)
    else:
        raise ValueError(f"Unknown framework: {framework}")


def get_serializer(framework: str) -> ArtifactSerializerInterface:
    framework = framework.lower()
    if framework == "sklearn":
        return SKLearnSerializer()
    elif framework == "pytorch":
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not installed")
        return PyTorchSerializer()
    elif framework in ("tensorflow", "tf", "keras"):
        if not TF_AVAILABLE:
            raise RuntimeError("TensorFlow not installed")
        return TensorFlowSerializer()
    else:
        raise ValueError(f"Unknown framework: {framework}")