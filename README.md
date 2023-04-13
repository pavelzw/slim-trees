# Slim Trees

[![CI](https://github.com/pavelzw/slim-trees/actions/workflows/ci.yml/badge.svg)](https://github.com/pavelzw/slim-trees/actions/workflows/ci.yml)
[![conda-forge](https://img.shields.io/conda/vn/conda-forge/slim-trees?logoColor=white&logo=conda-forge)](https://anaconda.org/conda-forge/slim-trees)
[![pypi-version](https://img.shields.io/pypi/v/slim-trees.svg?logo=pypi&logoColor=white)](https://pypi.org/project/slim-trees)
[![python-version](https://img.shields.io/pypi/pyversions/slim-trees?logoColor=white&logo=python)](https://pypi.org/project/slim-trees)

`slim-trees` is a Python package for saving and loading compressed `sklearn` Tree-based and `lightgbm` models.
The compression is performed by modifying how the model is pickled by Python's `pickle` module.

## Installation

```bash
pip install slim-trees
# or
mamba install slim-trees -c conda-forge
```

## Usage

Using `slim-trees` does not affect your training pipeline.
Simply call `dump_sklearn_compressed` instead of `pickle.dump` to save your model.

Example for a `RandomForestClassifier`:

```python
# example, you can also use other Tree-based models
from sklearn.ensemble import RandomForestClassifier
from slim_trees import dump_sklearn_compressed

# load training data
X, y = ...
model = RandomForestClassifier()
model.fit(X, y)

dump_sklearn_compressed(model, "model.pkl")
# or alternatively with compression
dump_sklearn_compressed(model, "model.pkl.lzma")
```

Example for a `LGBMRegressor`:

```python
from lightgbm import LGBMRegressor
from slim_trees import dump_lgbm_compressed

# load training data
X, y = ...
model = LGBMRegressor()
model.fit(X, y)

dump_lgbm_compressed(model, "model.pkl")
# or alternatively with compression
dump_lgbm_compressed(model, "model.pkl.lzma")
```

Later, you can load the model using `pickle.load` as usual.

```python
from slim_trees import load_compressed

model = load_compressed("model.pkl")
```

---

### drop-in replacement for pickle

```python
from slim_trees import sklearn_tree, lgbm_booster

# for sklearn models
with open("model.pkl", "wb") as f:
    sklearn_tree.dump(model, f)  # instead of pickle.dump(...)

# for lightgbm models
with open("model.pkl", "wb") as f:
    lgbm_booster.dump(model, f)  # instead of pickle.dump(...)
```

## Development Installation

You can install the package in development mode using:

```bash
git clone git@github.com:pavelzw/slim-trees.git
cd slim-trees

# create and activate a fresh environment named slim_trees
# see environment.yml for details
mamba env create
conda activate slim_trees

pre-commit install
pip install --no-build-isolation -e .
```

## Benchmark

As a general overview on what you can expect in terms of savings:
This is a 1.2G large sklearn `RandomForestRegressor`.

![benchmark](.github/assets/benchmark.png)

The new file is 9x smaller than the original pickle file.
