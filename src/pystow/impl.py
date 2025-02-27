# -*- coding: utf-8 -*-

"""Module implementation."""

import gzip
import json
import logging
import lzma
import tarfile
import warnings
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Optional, Sequence, Union

from . import utils
from .constants import JSON, Opener
from .utils import (
    download_from_google,
    download_from_s3,
    get_base,
    mkdir,
    name_from_s3_key,
    name_from_url,
    read_rdf,
    read_tarfile_csv,
    read_tarfile_xml,
    read_zip_np,
    read_zipfile_csv,
)

try:
    import pickle5 as pickle
except ImportError:
    import pickle  # type:ignore

if TYPE_CHECKING:
    import botocore.client
    import lxml.etree
    import pandas as pd
    import rdflib

__all__ = ["Module"]

logger = logging.getLogger(__name__)


class Module:
    """The class wrapping the directory lookup implementation."""

    def __init__(self, base: Union[str, Path], ensure_exists: bool = True) -> None:
        """Initialize the module.

        :param base:
            The base directory for the module
        :param ensure_exists:
            Should the base directory be created automatically?
            Defaults to true.
        """
        self.base = Path(base)
        mkdir(self.base, ensure_exists=ensure_exists)

    @classmethod
    def from_key(cls, key: str, *subkeys: str, ensure_exists: bool = True) -> "Module":
        """Get a module for the given directory or one of its subdirectories.

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
            A module
        """
        base = get_base(key, ensure_exists=False)
        rv = cls(base=base, ensure_exists=ensure_exists)
        if subkeys:
            rv = rv.module(*subkeys, ensure_exists=ensure_exists)
        return rv

    def submodule(self, *args, **kwargs) -> "Module":
        """Get a module for a subdirectory of the current module."""  # noqa
        warnings.warn("Use .module() instead", DeprecationWarning)
        return self.module(*args, **kwargs)

    def module(self, *subkeys: str, ensure_exists: bool = True) -> "Module":
        """Get a module for a subdirectory of the current module.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param ensure_exists:
            Should all directories be created automatically?
            Defaults to true.
        :return:
            A module representing the subdirectory based on the given ``subkeys``.
        """
        base = self.join(*subkeys, ensure_exists=False)
        return Module(base=base, ensure_exists=ensure_exists)

    def join(
        self,
        *subkeys: str,
        name: Optional[str] = None,
        ensure_exists: bool = True,
    ) -> Path:
        """Get a subdirectory of the current module.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param ensure_exists:
            Should all directories be created automatically?
            Defaults to true.
        :param name:
            The name of the file (optional) inside the folder
        :return:
            The path of the directory or subdirectory for the given module.
        """
        rv = self.base
        if subkeys:
            rv = rv.joinpath(*subkeys)
            mkdir(rv, ensure_exists=ensure_exists)
        if name:
            rv = rv.joinpath(name)
        return rv

    def joinpath_sqlite(self, *subkeys: str, name: str) -> str:
        """Get an SQLite database connection string.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param name: The name of the database file.
        :return: A SQLite path string.
        """
        path = self.join(*subkeys, name=name, ensure_exists=True)
        return f"sqlite:///{path.as_posix()}"

    def ensure(
        self,
        *subkeys: str,
        url: str,
        name: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> Path:
        """Ensure a file is downloaded.

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
        if name is None:
            name = name_from_url(url)
        path = self.join(*subkeys, name=name, ensure_exists=True)
        utils.download(
            url=url,
            path=path,
            force=force,
            **(download_kwargs or {}),
        )
        return path

    def ensure_untar(
        self,
        *subkeys: str,
        url: str,
        name: Optional[str] = None,
        directory: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
        extract_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> Path:
        """Ensure a tar file is downloaded and unarchived.

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
        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        if directory is None:
            # rhea-rxn.tar.gz -> rhea-rxn
            suffixes_len = sum(len(suffix) for suffix in path.suffixes)
            directory = path.name[:-suffixes_len]
        unzipped_path = path.parent.joinpath(directory)
        if unzipped_path.is_dir() and not force:
            return unzipped_path
        unzipped_path.mkdir(exist_ok=True, parents=True)
        with tarfile.open(path) as tar_file:
            tar_file.extractall(unzipped_path, **(extract_kwargs or {}))
        return unzipped_path

    @contextmanager
    def ensure_open(
        self,
        *subkeys: str,
        url: str,
        name: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
        mode: str = "r",
        open_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> Opener:
        """Ensure a file is downloaded and open it.

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

        :yields: An open file object
        """
        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        open_kwargs = {} if open_kwargs is None else dict(open_kwargs)
        open_kwargs.setdefault("mode", mode)
        with path.open(**open_kwargs) as file:
            yield file

    @contextmanager
    def open(
        self,
        *subkeys: str,
        name: str,
        mode: str = "r",
        open_kwargs: Optional[Mapping[str, Any]] = None,
        ensure_exists: bool = False,
    ) -> Opener:
        """Open a file that exists already.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param name: The name of the file to open
        :param mode: The read mode, passed to :func:`open`
        :param open_kwargs: Additional keyword arguments passed to :func:`open`
        :param ensure_exists: Should the file be made? Set to true on write operations.

        :yields: An open file object
        """
        path = self.join(*subkeys, name=name, ensure_exists=ensure_exists)
        open_kwargs = {} if open_kwargs is None else dict(open_kwargs)
        open_kwargs.setdefault("mode", mode)
        with path.open(**open_kwargs) as file:
            yield file

    @contextmanager
    def ensure_open_lzma(
        self,
        *subkeys: str,
        url: str,
        name: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
        mode: str = "rt",
        open_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> Opener:
        """Ensure a LZMA-compressed file is downloaded and open a file inside it.

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
        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        open_kwargs = {} if open_kwargs is None else dict(open_kwargs)
        open_kwargs.setdefault("mode", mode)
        with lzma.open(path, **open_kwargs) as file:
            yield file

    @contextmanager
    def ensure_open_tarfile(
        self,
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
        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        open_kwargs = {} if open_kwargs is None else dict(open_kwargs)
        open_kwargs.setdefault("mode", mode)
        with tarfile.open(path, **open_kwargs) as tar_file:
            with tar_file.extractfile(inner_path) as file:  # type:ignore
                yield file

    @contextmanager
    def ensure_open_zip(
        self,
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
        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        open_kwargs = {} if open_kwargs is None else dict(open_kwargs)
        open_kwargs.setdefault("mode", mode)
        with zipfile.ZipFile(file=path) as zip_file:
            with zip_file.open(inner_path) as file:
                yield file

    @contextmanager
    def ensure_open_gz(
        self,
        *subkeys: str,
        url: str,
        name: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
        mode: str = "rb",
        open_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> Opener:
        """Ensure a gzipped file is downloaded and open a file inside it.

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
        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        open_kwargs = {} if open_kwargs is None else dict(open_kwargs)
        open_kwargs.setdefault("mode", mode)
        with gzip.open(path, **open_kwargs) as file:
            yield file

    def ensure_csv(
        self,
        *subkeys: str,
        url: str,
        name: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
        read_csv_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> "pd.DataFrame":
        """Download a CSV and open as a dataframe with :mod:`pandas`.

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
        :rtype: pandas.DataFrame
        """
        import pandas as pd

        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        return pd.read_csv(path, **_clean_csv_kwargs(read_csv_kwargs))

    def load_df(
        self,
        *subkeys: str,
        name: str,
        read_csv_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> "pd.DataFrame":
        """Open a pre-existing CSV as a dataframe with :mod:`pandas`.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param name:
            Overrides the name of the file at the end of the URL, if given. Also
            useful for URLs that don't have proper filenames with extensions.
        :param read_csv_kwargs: Keyword arguments to pass through to :func:`pandas.read_csv`.
        :return: A pandas DataFrame
        """
        import pandas as pd

        with self.open(*subkeys, name=name) as file:
            return pd.read_csv(file, **_clean_csv_kwargs(read_csv_kwargs))

    def dump_df(
        self,
        *subkeys: str,
        name: str,
        obj: "pd.DataFrame",
        sep: str = "\t",
        index=False,
        to_csv_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Dump a dataframe to a TSV file with :mod:`pandas`.

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
        to_csv_kwargs = {} if to_csv_kwargs is None else dict(to_csv_kwargs)
        to_csv_kwargs.setdefault("sep", sep)
        to_csv_kwargs.setdefault("index", index)
        # should this use unified opener instead? Pandas is pretty smart...
        path = self.join(*subkeys, name=name)
        obj.to_csv(path, **to_csv_kwargs)

    def ensure_json(
        self,
        *subkeys: str,
        url: str,
        name: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
        json_load_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> JSON:
        """Download JSON and open with :mod:`json`.

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
        """
        with self.ensure_open(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        ) as file:
            return json.load(file, **(json_load_kwargs or {}))

    def load_json(
        self,
        *subkeys: str,
        name: str,
        open_kwargs: Optional[Mapping[str, Any]] = None,
        json_load_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> JSON:
        """Open a JSON file :mod:`json`.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param name: The name of the file to open
        :param open_kwargs: Additional keyword arguments passed to :func:`open`
        :param json_load_kwargs: Keyword arguments to pass through to :func:`json.load`.
        :returns: A JSON object (list, dict, etc.)
        """
        with self.open(
            *subkeys, name=name, mode="r", open_kwargs=open_kwargs, ensure_exists=True
        ) as file:
            return json.load(file, **(json_load_kwargs or {}))

    def dump_json(
        self,
        *subkeys: str,
        name: str,
        obj: JSON,
        open_kwargs: Optional[Mapping[str, Any]] = None,
        json_dump_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Dump an object to a file with :mod:`json`.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param name: The name of the file to open
        :param obj: The object to dump
        :param open_kwargs: Additional keyword arguments passed to :func:`open`
        :param json_dump_kwargs: Keyword arguments to pass through to :func:`json.dump`.
        """
        with self.open(
            *subkeys, name=name, mode="w", open_kwargs=open_kwargs, ensure_exists=True
        ) as file:
            json.dump(obj, file, **(json_dump_kwargs or {}))

    def ensure_pickle(
        self,
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
        with self.ensure_open(
            *subkeys,
            url=url,
            name=name,
            force=force,
            download_kwargs=download_kwargs,
            mode=mode,
            open_kwargs=open_kwargs,
        ) as file:
            return pickle.load(file, **(pickle_load_kwargs or {}))

    def load_pickle(
        self,
        *subkeys: str,
        name: str,
        mode: str = "rb",
        open_kwargs: Optional[Mapping[str, Any]] = None,
        pickle_load_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        """Open a pickle file with :mod:`pickle`.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param name: The name of the file to open
        :param mode: The read mode, passed to :func:`open`
        :param open_kwargs: Additional keyword arguments passed to :func:`open`
        :param pickle_load_kwargs: Keyword arguments to pass through to :func:`pickle.load`.
        :returns: Any object
        """
        with self.open(
            *subkeys,
            name=name,
            mode=mode,
            open_kwargs=open_kwargs,
        ) as file:
            return pickle.load(file, **(pickle_load_kwargs or {}))

    def dump_pickle(
        self,
        *subkeys: str,
        name: str,
        obj: Any,
        mode: str = "wb",
        open_kwargs: Optional[Mapping[str, Any]] = None,
        pickle_dump_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Dump an object to a file with :mod:`pickle`.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param name: The name of the file to open
        :param obj: The object to dump
        :param mode: The read mode, passed to :func:`open`
        :param open_kwargs: Additional keyword arguments passed to :func:`open`
        :param pickle_dump_kwargs: Keyword arguments to pass through to :func:`pickle.dump`.
        """
        with self.open(
            *subkeys,
            name=name,
            mode=mode,
            open_kwargs=open_kwargs,
        ) as file:
            pickle.dump(obj, file, **(pickle_dump_kwargs or {}))

    def ensure_excel(
        self,
        *subkeys: str,
        url: str,
        name: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
        read_excel_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> "pd.DataFrame":
        """Download an excel file and open as a dataframe with :mod:`pandas`.

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
        import pandas as pd

        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        return pd.read_excel(path, **(read_excel_kwargs or {}))

    def ensure_tar_df(
        self,
        *subkeys: str,
        url: str,
        inner_path: str,
        name: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
        read_csv_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> "pd.DataFrame":
        """Download a tar file and open an inner file as a dataframe with :mod:`pandas`.

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
        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        return read_tarfile_csv(
            path=path, inner_path=inner_path, **_clean_csv_kwargs(read_csv_kwargs)
        )

    def ensure_xml(
        self,
        *subkeys: str,
        url: str,
        name: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
        parse_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> "lxml.etree.ElementTree":
        """Download an XML file and open it with :mod:`lxml`.

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
        from lxml import etree

        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        return etree.parse(path, **(parse_kwargs or {}))

    def load_xml(
        self,
        *subkeys: str,
        name: str,
        parse_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> "lxml.etree.ElementTree":
        """Load an XML file with :mod:`lxml`.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param name: The name of the file to open
        :param parse_kwargs: Keyword arguments to pass through to :func:`lxml.etree.parse`.
        :returns: An ElementTree object

        .. warning:: If you have lots of files to read in the same archive, it's better just to unzip first.
        """
        from lxml import etree

        with self.open(*subkeys, name=name, ensure_exists=False) as file:
            return etree.parse(file, **(parse_kwargs or {}))

    def dump_xml(
        self,
        *subkeys: str,
        name: str,
        obj: "lxml.etree.ElementTree",
        open_kwargs: Optional[Mapping[str, Any]] = None,
        write_kwargs: Optional[Mapping[str, Any]] = None,
    ):
        """Dump an XML element tree to a file with :mod:`lxml`.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param name: The name of the file to open
        :param obj: The object to dump
        :param open_kwargs: Additional keyword arguments passed to :func:`open`
        :param write_kwargs: Keyword arguments to pass through to :func:`lxml.etree.ElementTree.write`.
        """
        with self.open(
            *subkeys, name=name, mode="wb", open_kwargs=open_kwargs, ensure_exists=True
        ) as file:
            obj.write(file, **(write_kwargs or {}))

    def ensure_tar_xml(
        self,
        *subkeys: str,
        url: str,
        inner_path: str,
        name: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
        parse_kwargs: Optional[Mapping[str, Any]] = None,
    ):
        """Download a tar file and open an inner file as an XML with :mod:`lxml`.

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
        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        return read_tarfile_xml(path=path, inner_path=inner_path, **(parse_kwargs or {}))

    def ensure_zip_df(
        self,
        *subkeys: str,
        url: str,
        inner_path: str,
        name: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
        read_csv_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> "pd.DataFrame":
        """Download a zip file and open an inner file as a dataframe with :mod:`pandas`.

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
        :rtype: pandas.DataFrame
        """
        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        return read_zipfile_csv(
            path=path, inner_path=inner_path, **_clean_csv_kwargs(read_csv_kwargs)
        )

    def ensure_zip_np(
        self,
        *subkeys: str,
        url: str,
        inner_path: str,
        name: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
        load_kwargs: Optional[Mapping[str, Any]] = None,
    ):
        """Download a zip file and open an inner file as an array-like with :mod:`numpy`.

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
        :rtype: numpy.typing.ArrayLike
        """
        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        return read_zip_np(path=path, inner_path=inner_path, **(load_kwargs or {}))

    def ensure_rdf(
        self,
        *subkeys: str,
        url: str,
        name: Optional[str] = None,
        force: bool = False,
        download_kwargs: Optional[Mapping[str, Any]] = None,
        precache: bool = True,
        parse_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> "rdflib.Graph":
        """Download a RDF file and open with :mod:`rdflib`.

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
        :rtype: rdflib.Graph
        """
        path = self.ensure(
            *subkeys, url=url, name=name, force=force, download_kwargs=download_kwargs
        )
        if not precache:
            return read_rdf(path=path, **(parse_kwargs or {}))

        cache_path = path.with_suffix(path.suffix + ".pickle.gz")
        if cache_path.exists() and not force:
            with gzip.open(cache_path, "rb") as file:
                return pickle.load(file)  # type: ignore

        rv = read_rdf(path=path, **(parse_kwargs or {}))
        with gzip.open(cache_path, "wb") as file:
            pickle.dump(rv, file, protocol=pickle.HIGHEST_PROTOCOL)  # type: ignore
        return rv

    def load_rdf(
        self,
        *subkeys: str,
        name: Optional[str] = None,
        parse_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> "rdflib.Graph":
        """Open an RDF file with :mod:`rdflib`.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param name: The name of the file to open
        :param parse_kwargs:
            Keyword arguments to pass through to :func:`pystow.utils.read_rdf` and transitively to
            :func:`rdflib.Graph.parse`.
        :return: An RDF graph
        """
        path = self.join(*subkeys, name=name, ensure_exists=False)
        return read_rdf(path=path, **(parse_kwargs or {}))

    def dump_rdf(
        self,
        *subkeys: str,
        name: str,
        obj: "rdflib.Graph",
        format: str = "turtle",
        serialize_kwargs: Optional[Mapping[str, Any]] = None,
    ):
        """Dump an RDF graph to a file with :mod:`rdflib`.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param name: The name of the file to open
        :param obj: The object to dump
        :param format: The format to dump in
        :param serialize_kwargs:
            Keyword arguments to through to :func:`rdflib.Graph.serialize`.
        """
        path = self.join(*subkeys, name=name, ensure_exists=False)
        serialize_kwargs = {} if serialize_kwargs is None else dict(serialize_kwargs)
        serialize_kwargs.setdefault("format", format)
        obj.serialize(path, **serialize_kwargs)

    def ensure_from_s3(
        self,
        *subkeys: str,
        s3_bucket: str,
        s3_key: Union[str, Sequence[str]],
        name: Optional[str] = None,
        client: Optional["botocore.client.BaseClient"] = None,
        client_kwargs: Optional[Mapping[str, Any]] = None,
        download_file_kwargs: Optional[Mapping[str, Any]] = None,
        force: bool = False,
    ) -> Path:
        """Ensure a file is downloaded.

        :param subkeys:
            A sequence of additional strings to join. If none are given,
            returns the directory for this module.
        :param s3_bucket:
            The S3 bucket name
        :param s3_key:
            The S3 key name
        :param name:
            Overrides the name of the file at the end of the S3 key, if given.
        :param client:
            A botocore client. If none given, one will be created automatically
        :param client_kwargs:
            Keyword arguments to be passed to the client on instantiation.
        :param download_file_kwargs:
            Keyword arguments to be passed to :func:`boto3.s3.transfer.S3Transfer.download_file`
        :param force:
            Should the download be done again, even if the path already exists?
            Defaults to false.
        :return:
            The path of the file that has been downloaded (or already exists)
        """
        if not isinstance(s3_key, str):
            s3_key = "/".join(s3_key)  # join sequence
        if name is None:
            name = name_from_s3_key(s3_key)
        path = self.join(*subkeys, name=name, ensure_exists=True)
        download_from_s3(
            s3_bucket=s3_bucket,
            s3_key=s3_key,
            path=path,
            client=client,
            client_kwargs=client_kwargs,
            force=force,
            download_file_kwargs=download_file_kwargs,
        )
        return path

    def ensure_from_google(
        self,
        *subkeys: str,
        name: str,
        file_id: str,
        force: bool = False,
    ) -> Path:
        """Ensure a file is downloaded from Google Drive.

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
        """
        path = self.join(*subkeys, name=name, ensure_exists=True)
        download_from_google(file_id, path, force=force)
        return path


def _clean_csv_kwargs(read_csv_kwargs):
    read_csv_kwargs = {} if read_csv_kwargs is None else dict(read_csv_kwargs)
    read_csv_kwargs.setdefault("sep", "\t")
    return read_csv_kwargs
