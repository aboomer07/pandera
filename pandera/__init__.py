"""A flexible and expressive pandas validation library."""
import platform

from pandera import errors, external_config, typing
from pandera.accessors import pandas_accessor
from pandera.api import extensions
from pandera.api.checks import Check
from pandera.api.hypotheses import Hypothesis
from pandera.api.pandas import (
    Column,
    DataFrameSchema,
    Index,
    MultiIndex,
    SeriesSchema,
)
from pandera.api.pandas.model import DataFrameModel, SchemaModel
from pandera.api.pandas.model_components import Field, check, dataframe_check
from pandera.dtypes import (
    Bool,
    Category,
    Complex,
    Complex64,
    Complex128,
    DataType,
    Date,
    DateTime,
    Decimal,
    Float,
    Float16,
    Float32,
    Float64,
    Int,
    Int8,
    Int16,
    Int32,
    Int64,
    String,
    Timedelta,
    Timestamp,
    UInt,
    UInt8,
    UInt16,
    UInt32,
    UInt64,
)
from pandera.engines.numpy_engine import Object
from pandera.engines.pandas_engine import (
    BOOL,
    INT8,
    INT16,
    INT32,
    INT64,
    PANDAS_1_2_0_PLUS,
    PANDAS_1_3_0_PLUS,
    STRING,
    UINT8,
    UINT16,
    UINT32,
    UINT64,
    pandas_version,
)

import pandera.backends

from pandera.schema_inference.pandas import infer_schema
from pandera.decorators import check_input, check_io, check_output, check_types
from pandera.version import __version__


if platform.system() != "Windows":
    # pylint: disable=ungrouped-imports
    from pandera.dtypes import Complex256, Float128


try:
    import dask.dataframe

    from pandera.accessors import dask_accessor
except ImportError:
    pass


try:
    import pyspark.pandas

    from pandera.accessors import pyspark_accessor
except ImportError:
    pass


try:
    import modin.pandas

    from pandera.accessors import modin_accessor
except ImportError:
    pass

__all__ = [
    # dtypes
    "Bool",
    "Category",
    "Complex",
    "Complex64",
    "Complex128",
    "Complex256",
    "DataType",
    "DateTime",
    "Float",
    "Float16",
    "Float32",
    "Float64",
    "Float128",
    "Int",
    "Int8",
    "Int16",
    "Int32",
    "Int64",
    "String",
    "Timedelta",
    "Timestamp",
    "UInt",
    "UInt8",
    "UInt16",
    "UInt32",
    "UInt64",
    # numpy_engine
    "Object",
    # pandas_engine
    "BOOL",
    "INT8",
    "INT16",
    "INT32",
    "INT64",
    "PANDAS_1_3_0_PLUS",
    "STRING",
    "UINT8",
    "UINT16",
    "UINT32",
    "UINT64",
    # pandera.engines.pandas_engine
    "pandas_version",
    # checks
    "Check",
    # decorators
    "check_input",
    "check_io",
    "check_output",
    "check_types",
    # hypotheses
    "Hypothesis",
    # model
    "DataFrameModel",
    "SchemaModel",
    # model_components
    "Field",
    "check",
    "dataframe_check",
    # schema_components
    "Column",
    "Index",
    "MultiIndex",
    # schema_inference
    "infer_schema",
    # schemas
    "DataFrameSchema",
    "SeriesSchema",
    # version
    "__version__",
]
