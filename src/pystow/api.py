# -*- coding: utf-8 -*-

"""API functions for PyStow."""

import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Optional, Sequence, Union

from .constants import JSON, Opener
from .impl import Module

if TYPE_CHECKING:
    import lxml.etree
    import numpy.typing
    import pandas as pd
    import rdflib

__all__ = [
    "submodule",
    "module",
    "join",
    "joinpath_sqlite",
    # Opener functions
    "open",
    "load_df",
    "load_json",
    "load_pickle",
    "load_rdf",
    "load_xml",
    # Dump functions
    "dump_df",
    "dump_json",
    "dump_pickle",
    "dump_rdf",
    "dump_xml",
    # Downloader functions
    "ensure",
    "ensure_from_s3",
    "ensure_from_google",
    # Downloader functions with postprocessing
    "ensure_untar",
    # Downloader + opener functions
    "ensure_open",
    "ensure_open_gz",
    "ensure_open_lzma",
    "ensure_open_tarfile",
    "ensure_open_zip",
    # Processors
    "ensure_csv",
    "ensure_json",
    "ensure_pickle",
    "ensure_excel",
    "ensure_xml",
    "ensure_rdf",
    "ensure_tar_df",
    "ensure_tar_xml",
    "ensure_zip_df",
    "ensure_zip_np",
]


def submodule(key: str, *subkeys: str, ensure_exists: bool = True) -> Module:
    """Return a module for the application."""  # noqa
    warnings.warn("Use .module() instead", DeprecationWarning)
    return module(key, *subkeys, ensure_exists=ensure_exists)


def module(key: str, *subkeys: str, ensure_exists: bool = True) -> Module:
    """Return a module for the application.

    :param key:
        The name of the module. No funny characters. The envvar
        <key>_HOME where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param ensure_exists:
        Should all directories be created automatically?
        Defaults to true.
    :return:
        The module object that manages getting and ensuring
    """
    return Module.from_key(key, *subkeys, ensure_exists=ensure_exists)


def join(key: str, *subkeys: str, name: Optional[str] = None, ensure_exists: bool = True) -> Path:
    """Return the home data directory for the given module.

    :param key:
        The name of the module. No funny characters. The envvar
        <key>_HOME where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join
    :param name:
        The name of the file (optional) inside the folder
    :param ensure_exists:
        Should all directories be created automatically?
        Defaults to true.
    :return:
        The path of the directory or subdirectory for the given module.
    """
    _module = Module.from_key(key, ensure_exists=ensure_exists)
    return _module.join(*subkeys, name=name, ensure_exists=ensure_exists)


@contextmanager
def open(
    key: str,
    *subkeys: str,
    name: str,
    mode: str = "r",
    open_kwargs: Optional[Mapping[str, Any]] = None,
):
    """Open a file that exists already.

    :param key:
        The name of the module. No funny characters. The envvar
        <key>_HOME where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param name: The name of the file to open
    :param mode: The read mode, passed to :func:`open`
    :param open_kwargs: Additional keyword arguments passed to :func:`open`

    :yields: An open file object
    """
    _module = Module.from_key(key, ensure_exists=True)
    with _module.open(*subkeys, name=name, mode=mode, open_kwargs=open_kwargs) as file:
        yield file


def ensure(
    key: str,
    *subkeys: str,
    url: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
) -> Path:
    """Ensure a file is downloaded.

    :param key:
        The name of the module. No funny characters. The envvar
        <key>_HOME where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :return:
        The path of the file that has been downloaded (or already exists)
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure(
        *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
    )


def ensure_untar(
    key: str,
    *subkeys: str,
    url: str,
    name: Optional[str] = None,
    directory: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    extract_kwargs: Optional[Mapping[str, Any]] = None,
) -> Path:
    """Ensure a file is downloaded and untarred.

    :param key:
        The name of the module. No funny characters. The envvar
        <key>_HOME where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param directory:
        Overrides the name of the directory into which the tar archive is extracted.
        If none given, will use the stem of the file name that gets downloaded.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param extract_kwargs: Keyword arguments to pass to :meth:`tarfile.TarFile.extract_all`.
    :return:
        The path of the directory where the file that has been downloaded
        gets extracted to
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure_untar(
        *subkeys,
        url=url,
        name=name,
        directory=directory,
        force=force,
        download_kwargs=download_kwargs,
        extract_kwargs=extract_kwargs,
    )


@contextmanager
def ensure_open(
    key: str,
    *subkeys: str,
    url: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    mode: str = "r",
    open_kwargs: Optional[Mapping[str, Any]] = None,
) -> Opener:
    """Ensure a file is downloaded and open it.

    :param key:
        The name of the module. No funny characters. The envvar
        `<key>_HOME` where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param mode: The read mode, passed to :func:`lzma.open`
    :param open_kwargs: Additional keyword arguments passed to :func:`lzma.open`

    :yields: An open file object
    """
    _module = Module.from_key(key, ensure_exists=True)
    with _module.ensure_open(
        *subkeys,
        url=url,
        name=name,
        force=force,
        download_kwargs=download_kwargs,
        mode=mode,
        open_kwargs=open_kwargs,
    ) as yv:
        yield yv


@contextmanager
def ensure_open_zip(
    key: str,
    *subkeys: str,
    url: str,
    inner_path: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    mode: str = "r",
    open_kwargs: Optional[Mapping[str, Any]] = None,
) -> Opener:
    """Ensure a file is downloaded then open it with :mod:`zipfile`.

    :param key:
        The name of the module. No funny characters. The envvar
        `<key>_HOME` where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param inner_path:
        The relative path to the file inside the archive
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param mode: The read mode, passed to :func:`zipfile.open`
    :param open_kwargs: Additional keyword arguments passed to :func:`zipfile.open`

    :yields: An open file object
    """
    _module = Module.from_key(key, ensure_exists=True)
    with _module.ensure_open_zip(
        *subkeys,
        url=url,
        inner_path=inner_path,
        name=name,
        force=force,
        download_kwargs=download_kwargs,
        mode=mode,
        open_kwargs=open_kwargs,
    ) as yv:
        yield yv


@contextmanager
def ensure_open_lzma(
    key: str,
    *subkeys: str,
    url: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    mode: str = "r",
    open_kwargs: Optional[Mapping[str, Any]] = None,
) -> Opener:
    """Ensure a LZMA-compressed file is downloaded and open a file inside it.

    :param key:
        The name of the module. No funny characters. The envvar
        `<key>_HOME` where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param mode: The read mode, passed to :func:`lzma.open`
    :param open_kwargs: Additional keyword arguments passed to :func:`lzma.open`

    :yields: An open file object
    """
    _module = Module.from_key(key, ensure_exists=True)
    with _module.ensure_open_lzma(
        *subkeys,
        url=url,
        name=name,
        force=force,
        download_kwargs=download_kwargs,
        mode=mode,
        open_kwargs=open_kwargs,
    ) as yv:
        yield yv


@contextmanager
def ensure_open_tarfile(
    key: str,
    *subkeys: str,
    url: str,
    inner_path: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    mode: str = "r",
    open_kwargs: Optional[Mapping[str, Any]] = None,
) -> Opener:
    """Ensure a tar file is downloaded and open a file inside it.

    :param key:
        The name of the module. No funny characters. The envvar
        `<key>_HOME` where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param inner_path:
        The relative path to the file inside the archive
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param mode: The read mode, passed to :func:`tarfile.open`
    :param open_kwargs: Additional keyword arguments passed to :func:`tarfile.open`

    :yields: An open file object
    """
    _module = Module.from_key(key, ensure_exists=True)
    with _module.ensure_open_tarfile(
        *subkeys,
        url=url,
        inner_path=inner_path,
        name=name,
        force=force,
        download_kwargs=download_kwargs,
        mode=mode,
        open_kwargs=open_kwargs,
    ) as yv:
        yield yv


@contextmanager
def ensure_open_gz(
    key: str,
    *subkeys: str,
    url: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    mode: str = "rb",
    open_kwargs: Optional[Mapping[str, Any]] = None,
) -> Opener:
    """Ensure a gzipped file is downloaded and open a file inside it.

    :param key:
        The name of the module. No funny characters. The envvar
        `<key>_HOME` where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param mode: The read mode, passed to :func:`gzip.open`
    :param open_kwargs: Additional keyword arguments passed to :func:`gzip.open`

    :yields: An open file object
    """
    _module = Module.from_key(key, ensure_exists=True)
    with _module.ensure_open_gz(
        *subkeys,
        url=url,
        name=name,
        force=force,
        download_kwargs=download_kwargs,
        mode=mode,
        open_kwargs=open_kwargs,
    ) as yv:
        yield yv


def ensure_csv(
    key: str,
    *subkeys: str,
    url: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    read_csv_kwargs: Optional[Mapping[str, Any]] = None,
) -> "pd.DataFrame":
    """Download a CSV and open as a dataframe with :mod:`pandas`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param read_csv_kwargs: Keyword arguments to pass through to :func:`pandas.read_csv`.
    :return: A pandas DataFrame

    Example usage::

    >>> import pystow
    >>> import pandas as pd
    >>> url = 'https://raw.githubusercontent.com/pykeen/pykeen/master/src/pykeen/datasets/nations/test.txt'
    >>> df: pd.DataFrame = pystow.ensure_csv('pykeen', 'datasets', 'nations', url=url)
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure_csv(
        *subkeys,
        url=url,
        name=name,
        force=force,
        download_kwargs=download_kwargs,
        read_csv_kwargs=read_csv_kwargs,
    )


def load_df(
    key: str,
    *subkeys: str,
    name: str,
    read_csv_kwargs: Optional[Mapping[str, Any]] = None,
) -> "pd.DataFrame":
    """Open a pre-existing CSV as a dataframe with :mod:`pandas`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param read_csv_kwargs: Keyword arguments to pass through to :func:`pandas.read_csv`.
    :return: A pandas DataFrame

    Example usage::

    >>> import pystow
    >>> import pandas as pd
    >>> url = 'https://raw.githubusercontent.com/pykeen/pykeen/master/src/pykeen/datasets/nations/test.txt'
    >>> pystow.ensure_csv('pykeen', 'datasets', 'nations', url=url)
    >>> df: pd.DataFrame = pystow.load_df('pykeen', 'datasets', 'nations', name='test.txt')
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.load_df(
        *subkeys,
        name=name,
        read_csv_kwargs=read_csv_kwargs,
    )


def dump_df(
    key: str,
    *subkeys: str,
    name: str,
    obj: "pd.DataFrame",
    sep: str = "\t",
    index=False,
    to_csv_kwargs: Optional[Mapping[str, Any]] = None,
) -> None:
    """Dump a dataframe to a TSV file with :mod:`pandas`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param obj: The dataframe to dump
    :param sep: The separator to use, defaults to a tab
    :param index: Should the index be dumped? Defaults to false.
    :param to_csv_kwargs: Keyword arguments to pass through to :meth:`pandas.DataFrame.to_csv`.
    """
    _module = Module.from_key(key, ensure_exists=True)
    _module.dump_df(
        *subkeys,
        name=name,
        obj=obj,
        sep=sep,
        index=index,
        to_csv_kwargs=to_csv_kwargs,
    )


def ensure_json(
    key: str,
    *subkeys: str,
    url: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    json_load_kwargs: Optional[Mapping[str, Any]] = None,
) -> JSON:
    """Download JSON and open with :mod:`json`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param json_load_kwargs: Keyword arguments to pass through to :func:`json.load`.
    :returns: A JSON object (list, dict, etc.)

    Example usage::

    >>> import pystow
    >>> url = 'https://maayanlab.cloud/CREEDS/download/single_gene_perturbations-v1.0.json'
    >>> perturbations = pystow.ensure_json('bio', 'creeds', '1.0', url=url)
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure_json(
        *subkeys,
        url=url,
        name=name,
        force=force,
        download_kwargs=download_kwargs,
        json_load_kwargs=json_load_kwargs,
    )


def load_json(
    key: str,
    *subkeys: str,
    name: str,
    json_load_kwargs: Optional[Mapping[str, Any]] = None,
) -> JSON:
    """Open a JSON file :mod:`json`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param name: The name of the file to open
    :param json_load_kwargs: Keyword arguments to pass through to :func:`json.load`.
    :returns: A JSON object (list, dict, etc.)
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.load_json(*subkeys, name=name, json_load_kwargs=json_load_kwargs)


def dump_json(
    key: str,
    *subkeys: str,
    name: str,
    obj: JSON,
    open_kwargs: Optional[Mapping[str, Any]] = None,
    json_dump_kwargs: Optional[Mapping[str, Any]] = None,
) -> None:
    """Dump an object to a file with :mod:`json`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param name: The name of the file to open
    :param obj: The object to dump
    :param open_kwargs: Additional keyword arguments passed to :func:`open`
    :param json_dump_kwargs: Keyword arguments to pass through to :func:`json.dump`.
    """
    _module = Module.from_key(key, ensure_exists=True)
    _module.dump_json(
        *subkeys, name=name, obj=obj, open_kwargs=open_kwargs, json_dump_kwargs=json_dump_kwargs
    )


def ensure_pickle(
    key: str,
    *subkeys: str,
    url: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    mode: str = "rb",
    open_kwargs: Optional[Mapping[str, Any]] = None,
    pickle_load_kwargs: Optional[Mapping[str, Any]] = None,
) -> Any:
    """Download a pickle file and open with :mod:`pickle`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param mode: The read mode, passed to :func:`open`
    :param open_kwargs: Additional keyword arguments passed to :func:`open`
    :param pickle_load_kwargs: Keyword arguments to pass through to :func:`pickle.load`.
    :returns: Any object
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure_pickle(
        *subkeys,
        url=url,
        name=name,
        force=force,
        download_kwargs=download_kwargs,
        mode=mode,
        open_kwargs=open_kwargs,
        pickle_load_kwargs=pickle_load_kwargs,
    )


def load_pickle(
    key: str,
    *subkeys: str,
    name: str,
    mode: str = "rb",
    open_kwargs: Optional[Mapping[str, Any]] = None,
    pickle_load_kwargs: Optional[Mapping[str, Any]] = None,
) -> Any:
    """Open a pickle file with :mod:`pickle`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param name: The name of the file to open
    :param mode: The read mode, passed to :func:`open`
    :param open_kwargs: Additional keyword arguments passed to :func:`open`
    :param pickle_load_kwargs: Keyword arguments to pass through to :func:`pickle.load`.
    :returns: Any object
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.load_pickle(
        *subkeys,
        name=name,
        mode=mode,
        open_kwargs=open_kwargs,
        pickle_load_kwargs=pickle_load_kwargs,
    )


def dump_pickle(
    key: str,
    *subkeys: str,
    name: str,
    obj: Any,
    mode: str = "wb",
    open_kwargs: Optional[Mapping[str, Any]] = None,
    pickle_dump_kwargs: Optional[Mapping[str, Any]] = None,
) -> None:
    """Dump an object to a file with :mod:`pickle`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param name: The name of the file to open
    :param obj: The object to dump
    :param mode: The read mode, passed to :func:`open`
    :param open_kwargs: Additional keyword arguments passed to :func:`open`
    :param pickle_dump_kwargs: Keyword arguments to pass through to :func:`pickle.dump`.
    """
    _module = Module.from_key(key, ensure_exists=True)
    _module.dump_pickle(
        *subkeys,
        name=name,
        obj=obj,
        mode=mode,
        open_kwargs=open_kwargs,
        pickle_dump_kwargs=pickle_dump_kwargs,
    )


def ensure_xml(
    key: str,
    *subkeys: str,
    url: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    parse_kwargs: Optional[Mapping[str, Any]] = None,
) -> "lxml.etree.ElementTree":
    """Download an XML file and open it with :mod:`lxml`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param parse_kwargs: Keyword arguments to pass through to :func:`lxml.etree.parse`.
    :returns: An ElementTree object

    .. warning:: If you have lots of files to read in the same archive, it's better just to unzip first.
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure_xml(
        *subkeys,
        name=name,
        url=url,
        force=force,
        download_kwargs=download_kwargs,
        parse_kwargs=parse_kwargs,
    )


def load_xml(
    key: str,
    *subkeys: str,
    name: str,
    parse_kwargs: Optional[Mapping[str, Any]] = None,
) -> "lxml.etree.ElementTree":
    """Load an XML file with :mod:`lxml`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param name: The name of the file to open
    :param parse_kwargs: Keyword arguments to pass through to :func:`lxml.etree.parse`.
    :returns: An ElementTree object

    .. warning:: If you have lots of files to read in the same archive, it's better just to unzip first.
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.load_xml(
        *subkeys,
        name=name,
        parse_kwargs=parse_kwargs,
    )


def dump_xml(
    key: str,
    *subkeys: str,
    name: str,
    obj: "lxml.etree.ElementTree",
    open_kwargs: Optional[Mapping[str, Any]] = None,
    write_kwargs: Optional[Mapping[str, Any]] = None,
) -> None:
    """Dump an XML element tree to a file with :mod:`lxml`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param name: The name of the file to open
    :param obj: The object to dump
    :param open_kwargs: Additional keyword arguments passed to :func:`open`
    :param write_kwargs: Keyword arguments to pass through to :func:`lxml.etree.ElementTree.write`.
    """
    _module = Module.from_key(key, ensure_exists=True)
    _module.dump_xml(
        *subkeys,
        name=name,
        obj=obj,
        open_kwargs=open_kwargs,
        write_kwargs=write_kwargs,
    )


def ensure_excel(
    key: str,
    *subkeys: str,
    url: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    read_excel_kwargs: Optional[Mapping[str, Any]] = None,
) -> "pd.DataFrame":
    """Download an excel file and open as a dataframe with :mod:`pandas`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param read_excel_kwargs: Keyword arguments to pass through to :func:`pandas.read_excel`.
    :return: A pandas DataFrame
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure_excel(
        *subkeys,
        url=url,
        name=name,
        force=force,
        download_kwargs=download_kwargs,
        read_excel_kwargs=read_excel_kwargs,
    )


def ensure_tar_df(
    key: str,
    *subkeys: str,
    url: str,
    inner_path: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    read_csv_kwargs: Optional[Mapping[str, Any]] = None,
):
    """Download a tar file and open an inner file as a dataframe with :mod:`pandas`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param inner_path:
        The relative path to the file inside the archive
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param read_csv_kwargs: Keyword arguments to pass through to :func:`pandas.read_csv`.
    :returns: A dataframe

    .. warning:: If you have lots of files to read in the same archive, it's better just to unzip first.
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure_tar_df(
        *subkeys,
        url=url,
        name=name,
        force=force,
        inner_path=inner_path,
        download_kwargs=download_kwargs,
        read_csv_kwargs=read_csv_kwargs,
    )


def ensure_tar_xml(
    key: str,
    *subkeys: str,
    url: str,
    inner_path: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    parse_kwargs: Optional[Mapping[str, Any]] = None,
):
    """Download a tar file and open an inner file as an XML with :mod:`lxml`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param inner_path:
        The relative path to the file inside the archive
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param parse_kwargs: Keyword arguments to pass through to :func:`lxml.etree.parse`.
    :returns: An ElementTree object

    .. warning:: If you have lots of files to read in the same archive, it's better just to unzip first.
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure_tar_xml(
        *subkeys,
        url=url,
        name=name,
        force=force,
        inner_path=inner_path,
        download_kwargs=download_kwargs,
        parse_kwargs=parse_kwargs,
    )


def ensure_zip_df(
    key: str,
    *subkeys: str,
    url: str,
    inner_path: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    read_csv_kwargs: Optional[Mapping[str, Any]] = None,
) -> "pd.DataFrame":
    """Download a zip file and open an inner file as a dataframe with :mod:`pandas`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param inner_path:
        The relative path to the file inside the archive
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param read_csv_kwargs: Keyword arguments to pass through to :func:`pandas.read_csv`.
    :return: A pandas DataFrame
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure_zip_df(
        *subkeys,
        url=url,
        name=name,
        force=force,
        inner_path=inner_path,
        download_kwargs=download_kwargs,
        read_csv_kwargs=read_csv_kwargs,
    )


def ensure_zip_np(
    key: str,
    *subkeys: str,
    url: str,
    inner_path: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    load_kwargs: Optional[Mapping[str, Any]] = None,
) -> "numpy.typing.ArrayLike":
    """Download a zip file and open an inner file as an array-like with :mod:`numpy`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param inner_path:
        The relative path to the file inside the archive
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs:
        Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param load_kwargs:
        Additional keyword arguments that are passed through to :func:`read_zip_np`
        and transitively to :func:`numpy.load`.
    :returns: An array-like object
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure_zip_np(
        *subkeys,
        url=url,
        name=name,
        force=force,
        inner_path=inner_path,
        download_kwargs=download_kwargs,
        load_kwargs=load_kwargs,
    )


def ensure_rdf(
    key: str,
    *subkeys: str,
    url: str,
    name: Optional[str] = None,
    force: bool = False,
    download_kwargs: Optional[Mapping[str, Any]] = None,
    precache: bool = True,
    parse_kwargs: Optional[Mapping[str, Any]] = None,
) -> "rdflib.Graph":
    """Download a RDF file and open with :mod:`rdflib`.

    :param key: The module name
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param url:
        The URL to download.
    :param name:
        Overrides the name of the file at the end of the URL, if given. Also
        useful for URLs that don't have proper filenames with extensions.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param download_kwargs: Keyword arguments to pass through to :func:`pystow.utils.download`.
    :param precache: Should the parsed :class:`rdflib.Graph` be stored as a pickle for fast loading?
    :param parse_kwargs:
        Keyword arguments to pass through to :func:`pystow.utils.read_rdf` and transitively to
        :func:`rdflib.Graph.parse`.
    :return: An RDF graph

    Example usage::

    >>> import pystow
    >>> import rdflib
    >>> url = 'https://ftp.expasy.org/databases/rhea/rdf/rhea.rdf.gz'
    >>> rdf_graph: rdflib.Graph = pystow.ensure_rdf('rhea', url=url)

    If :mod:`rdflib` fails to guess the format, you can explicitly specify it using the `parse_kwargs` argument:

    >>> import pystow
    >>> import rdflib
    >>> url = "http://oaei.webdatacommons.org/tdrs/testdata/persistent/knowledgegraph" \
    ... "/v3/suite/memoryalpha-stexpanded/component/reference.xml"
    >>> rdf_graph: rdflib.Graph = pystow.ensure_rdf("memoryalpha-stexpanded", url=url, parse_kwargs={"format": "xml"})
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure_rdf(
        *subkeys,
        url=url,
        name=name,
        force=force,
        download_kwargs=download_kwargs,
        precache=precache,
        parse_kwargs=parse_kwargs,
    )


def load_rdf(
    key: str,
    *subkeys: str,
    name: Optional[str] = None,
    parse_kwargs: Optional[Mapping[str, Any]] = None,
) -> "rdflib.Graph":
    """Open an RDF file with :mod:`rdflib`.

    :param key:
        The name of the module. No funny characters. The envvar
        <key>_HOME where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param name: The name of the file to open
    :param parse_kwargs:
        Keyword arguments to pass through to :func:`pystow.utils.read_rdf` and transitively to
        :func:`rdflib.Graph.parse`.
    :return: An RDF graph
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.load_rdf(*subkeys, name=name, parse_kwargs=parse_kwargs)


def dump_rdf(
    key: str,
    *subkeys: str,
    name: str,
    obj: "rdflib.Graph",
    format: str = "turtle",
    serialize_kwargs: Optional[Mapping[str, Any]] = None,
):
    """Dump an RDF graph to a file with :mod:`rdflib`.

    :param key:
        The name of the module. No funny characters. The envvar
        <key>_HOME where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param name: The name of the file to open
    :param obj: The object to dump
    :param format: The format to dump in
    :param serialize_kwargs:
        Keyword arguments to through to :func:`rdflib.Graph.serialize`.
    """
    _module = Module.from_key(key, ensure_exists=True)
    _module.dump_rdf(*subkeys, name=name, obj=obj, format=format, serialize_kwargs=serialize_kwargs)


def ensure_from_s3(
    key: str,
    *subkeys: str,
    s3_bucket: str,
    s3_key: Union[str, Sequence[str]],
    name: Optional[str] = None,
    force: bool = False,
    **kwargs,
) -> Path:
    """Ensure a file is downloaded.

    :param key:
        The name of the module. No funny characters. The envvar
        <key>_HOME where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param s3_bucket:
        The S3 bucket name
    :param s3_key:
        The S3 key name
    :param name:
        Overrides the name of the file at the end of the S3 key, if given.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :param kwargs:
        Remaining kwargs to forwrad to :class:`Module.ensure_from_s3`.
    :return:
        The path of the file that has been downloaded (or already exists)

    Example downloading ProtMapper 0.0.21:

    >>> version = '0.0.21'
    >>> ensure_from_s3('test', version, s3_bucket='bigmech', s3_key=f'protmapper/{version}/refseq_uniprot.csv')
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure_from_s3(
        *subkeys, s3_bucket=s3_bucket, s3_key=s3_key, name=name, force=force
    )


def ensure_from_google(
    key: str,
    *subkeys: str,
    name: str,
    file_id: str,
    force: bool = False,
) -> Path:
    """Ensure a file is downloaded from google drive.

    :param key:
        The name of the module. No funny characters. The envvar
        <key>_HOME where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param name:
        The name of the file
    :param file_id:
        The file identifier of the google file. If your share link is
        https://drive.google.com/file/d/1AsPPU4ka1Rc9u-XYMGWtvV65hF3egi0z/view, then your file id is
        ``1AsPPU4ka1Rc9u-XYMGWtvV65hF3egi0z``.
    :param force:
        Should the download be done again, even if the path already exists?
        Defaults to false.
    :return:
        The path of the file that has been downloaded (or already exists)

    Example downloading the WK3l-15k dataset as motivated by
    https://github.com/pykeen/pykeen/pull/403:

    >>> ensure_from_google('test', name='wk3l15k.zip', file_id='1AsPPU4ka1Rc9u-XYMGWtvV65hF3egi0z')
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.ensure_from_google(*subkeys, name=name, file_id=file_id, force=force)


def joinpath_sqlite(key: str, *subkeys: str, name: str) -> str:
    """Get an SQLite database connection string.

    :param key:
        The name of the module. No funny characters. The envvar
        `<key>_HOME` where key is uppercased is checked first before using
        the default home directory.
    :param subkeys:
        A sequence of additional strings to join. If none are given,
        returns the directory for this module.
    :param name: The name of the database file.
    :return: A SQLite path string.
    """
    _module = Module.from_key(key, ensure_exists=True)
    return _module.joinpath_sqlite(*subkeys, name=name)
