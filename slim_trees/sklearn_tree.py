import os
import sys

from slim_trees import __version__ as slim_trees_version
from slim_trees.compression_utils import (
    compress_half_int_float_array,
    decompress_half_int_float_array,
)
from slim_trees.utils import check_version

try:
    from sklearn.tree._tree import Tree
except ImportError:
    print("scikit-learn does not seem to be installed.")
    sys.exit(os.EX_CONFIG)

import copyreg
import pickle
from typing import Any, BinaryIO

import numpy as np


def dump_sklearn(model: Any, file: BinaryIO):
    p = pickle.Pickler(file)
    p.dispatch_table = copyreg.dispatch_table.copy()
    p.dispatch_table[Tree] = _tree_pickle
    p.dump(model)


def _tree_pickle(tree):
    assert isinstance(tree, Tree)
    reconstructor, args, state = tree.__reduce__()
    compressed_state = _compress_tree_state(state)
    return _tree_unpickle, (reconstructor, args, (slim_trees_version, compressed_state))


def _tree_unpickle(reconstructor, args, compressed_state):
    version, state = compressed_state
    check_version(version)

    tree = reconstructor(*args)
    decompressed_state = _decompress_tree_state(state)
    tree.__setstate__(decompressed_state)
    return tree


def _shrink_array(arr):
    if arr.dtype == "bool":
        return (np.packbits(arr).tobytes(), len(arr))
    else:
        dtype = arr.dtype
        assert str(dtype).startswith(("int", "uint"))
        min_val = arr.min()
        if min_val < 0:
            arr = arr - min_val
        arr = arr.astype(np.min_scalar_type(arr.max()))
        if min_val < 0:
            return (dtype, min_val, arr)
        else:
            return (dtype, arr)


def _unshrink_array(tpl):
    if isinstance(tpl, np.ndarray):
        return tpl
    if isinstance(tpl[0], bytes):
        bytes_, len_ = tpl
        return np.unpackbits(np.frombuffer(bytes_, dtype="uint8"), count=len_).astype(
            "bool"
        )
    elif len(tpl) == 3:  # noqa
        dtype, min_val, arr = tpl
        arr += min_val
    else:
        dtype, arr = tpl
    return arr.astype(dtype)


def _compress_tree_state(state: dict):
    """
    Compresses a Tree state.
    :param state: dictionary with 'max_depth', 'node_count', 'nodes', 'values' as keys.
    :return: dictionary with compressed tree state, only with data that is relevant for prediction.
    """
    assert isinstance(state, dict)
    assert state.keys() == {"max_depth", "node_count", "nodes", "values"}
    nodes = state["nodes"]
    # nodes is a numpy array of tuples of the following form
    # (left_child, right_child, feature, threshold, impurity, n_node_samples,
    #  weighted_n_node_samples)

    children_left = nodes["left_child"]
    children_right = nodes["right_child"]

    is_leaf = children_left == -1
    # assert that the leaves are the same no matter if you use children_left or children_right
    assert np.array_equal(is_leaf, children_right == -1)

    # feature, threshold and children are irrelevant when leaf
    children_left = children_left[~is_leaf]
    children_right = children_right[~is_leaf]
    features = nodes["feature"][~is_leaf]
    # value is irrelevant when node not a leaf
    values = state["values"][is_leaf].astype("float32")
    # do lossless compression for thresholds by downcasting half ints (e.g. 5.5, 10.5, ...) to int8
    thresholds = nodes["threshold"][~is_leaf].astype("float64")
    thresholds = compress_half_int_float_array(thresholds)
    thresholds["is_compressible"] = _shrink_array(thresholds["is_compressible"])

    return {
        "max_depth": state["max_depth"],
        "node_count": state["node_count"],
        "is_leaf": _shrink_array(is_leaf),
        "children_left": _shrink_array(children_left),
        "children_right": _shrink_array(children_right),
        "features": _shrink_array(features),
        "thresholds": thresholds,
        "values": values,
    }


def _decompress_tree_state(state: dict):
    """
    Decompresses a Tree state.
    :param state: 'children_left', 'children_right', 'features', 'thresholds', 'values' as keys.
                  'max_depth' and 'node_count' are passed through.
    :return: dictionary with decompressed tree state.
    """
    assert isinstance(state, dict)
    assert state.keys() == {
        "max_depth",
        "node_count",
        "is_leaf",
        "children_left",
        "children_right",
        "features",
        "thresholds",
        "values",
    }
    n_nodes = state["node_count"]

    children_left = np.zeros(n_nodes, dtype=np.int64)
    children_right = np.zeros(n_nodes, dtype=np.int64)
    features = np.zeros(n_nodes, dtype=np.int64)
    thresholds = np.zeros(n_nodes, dtype=np.float64)
    # same shape as values but with all nodes instead of only the leaves
    values = np.zeros((n_nodes, *state["values"].shape[1:]), dtype=np.float64)

    is_leaf = _unshrink_array(state["is_leaf"])
    children_left[~is_leaf] = _unshrink_array(state["children_left"])
    children_left[is_leaf] = -1
    children_right[~is_leaf] = _unshrink_array(state["children_right"])
    children_right[is_leaf] = -1
    features[~is_leaf] = _unshrink_array(state["features"])
    features[is_leaf] = -2  # feature of leaves is -2
    state["thresholds"]["is_compressible"] = _unshrink_array(
        state["thresholds"]["is_compressible"]
    )
    thresholds[~is_leaf] = decompress_half_int_float_array(state["thresholds"])
    thresholds[is_leaf] = -2.0  # threshold of leaves is -2
    values[is_leaf] = state["values"]

    dtype = np.dtype(
        [
            ("left_child", "<i8"),
            ("right_child", "<i8"),
            ("feature", "<i8"),
            ("threshold", "<f8"),
            ("impurity", "<f8"),
            ("n_node_samples", "<i8"),
            ("weighted_n_node_samples", "<f8"),
        ]
    )
    nodes = np.zeros(n_nodes, dtype=dtype)
    nodes["left_child"] = children_left
    nodes["right_child"] = children_right
    nodes["feature"] = features
    nodes["threshold"] = thresholds

    return {
        "max_depth": state["max_depth"],
        "node_count": state["node_count"],
        "nodes": nodes,
        "values": values,
    }
