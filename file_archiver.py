import argparse
import logging
import sys
import tarfile

from datetime import datetime
from grp import getgrnam
from logging import Logger
from os import getcwd, lstat, walk
from os.path import exists, isdir, join
from pwd import getpwnam
from typing import Tuple, Union


class FileCollector:

    def __init__(self, user_ids: list, base_path: str, logging: Logger):
        self.__user_ids = user_ids
        self.__path = base_path
        self.__logger = logging
        # the exclude directory collects all directories that are owned by the group as keys
        # The files that are found in these directories that are not owned by the group are saved as the value
        # while archiving those files are excluded from the process
        self.__exclude = {}
        self.__collect()

    def __collect(self) -> None:
        """
        Collecting of all files and directories owned by the given group
        """
        save_files = []
        num_found_files = 0
        num_found_dirs = 0
        num_exclude_files = 0
        if self.__lstat_wrapper(self.__path):
            # if the given root path is owned by the given group add it as key entry to the exclude directoy
            self.__exclude[self.__path] = list()
        # walking the complete file tree
        for root, dirs, files in walk(self.__path):
            # check if the current directory is owned by the group
            root_check, root_entry = self.__check_root_dir(root)
            if not root_check:
                # if the current root directory is not owned by the group the files and directories that are found in it and belong to the group are saved
                num_found_files += len([element for element in files if self.__lstat_wrapper(join(root, element))])
                num_found_dirs += len([element for element in dirs if self.__lstat_wrapper(join(root, element))])
                save_files.extend(element for element in map(lambda x: join(root, x), files) if self.__lstat_wrapper(element))
                self.__exclude.update({
                    entry: list() for entry in map(lambda x: join(root, x), dirs)
                    if self.__lstat_wrapper(entry)
                })
            else:
                # else the current found files which are not owned by the group are marked as to exclude
                num_exclude_files += len([element for element in files if not self.__lstat_wrapper(join(root, element))])
                self.__exclude[root_entry].extend(
                    element for element in map(lambda x: join(root, x), files)
                    if not self.__lstat_wrapper(element))

        # logging some basic informations
        self.__logger.info(f"Found {num_found_files} files owned by the group that were placed in directories not owned by the group")
        self.__logger.info(f"Found {num_found_dirs} directories owned by the group that were placed in directories not owned by the group")
        self.__logger.info(f"Found {num_exclude_files} files not owned by the group that were placed in directories owned by the group")
        # for easier usage the found files in other directories are add to the exclude list with empty list values
        self.__exclude.update({entry: list() for entry in save_files})

    def __check_root_dir(self, root_dir: str) -> Tuple[bool, Union[str, None]]:
        """
        Checking if the given directory is owned by the group
        """
        for element in self.__exclude:
            # for each saved root directory check if it fits the start of the given root directory.
            if root_dir.startswith(element):
                # The directory root of the directory is owned by the group, therefore the root is returned
                return True, element
        return False, None

    def __lstat_wrapper(self, entry: str) -> bool:
        """
        The lstat function fails if the given path has no clear permission and owner. And also if the file was temporary.
        It therefore catches these cases and gives the signal to skip this file
        """
        try:
            l_stat_element = lstat(entry)
        except (PermissionError, FileNotFoundError):
            l_stat_element = None
        return l_stat_element is not None and l_stat_element.st_uid in self.__user_ids

    def create_archive(self, s_path: str, tarball_name: str, compress_mode: str) -> None:
        """
        Saving the found dirs and files to a tarball
        """
        with tarfile.open(join(s_path, tarball_name), mode=compress_mode) as tar_ball:
            for element, exclude in self.__exclude.items():
                tar_ball.add(element, filter=lambda x: None if any(map(lambda y: y.endswith(x.name), exclude)) else x)


def setup_arg_parse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Processing arguments for the file archive program")
    parser.add_argument("gname", type=str, help="group name on which to work on")
    parser.add_argument("-bpath", "--base_path", type=str, default="/",
                        help="The base path on which to search on (default: /)")
    parser.add_argument("-spath", "--save_path", type=str, default="/tmp",
                        help="The path where the tar file is being saved (default: /tmp)")
    parser.add_argument("-lpath", "--logging_path", type=str, default=".",
                        help="The path where the tar file is being saved (default: .)")
    parser.add_argument("-c", "--no_compression", default=False, action="store_true",
                        help="Activating the compression for the archive (default: False)")
    return parser


if __name__ == "__main__":
    parser = setup_arg_parse()
    args = parser.parse_args()

    logging_file = args.logging_path
    if logging_file == ".":
        logging_file = getcwd()
    logging_file_base = logging_file
    current_time_stamp = None
    if not exists(logging_file):
        raise FileExistsError(
            "The given path does not exist, please provide a valid path for logging or use the default value")
    elif isdir(logging_file):
        current_time_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logging_file = join(logging_file_base, current_time_stamp + "_file_archiver.log")
        additional = 1
        while exists(logging_file):
            current_time_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            logging_file = join(logging_file_base, current_time_stamp + "_file_archiver.log." + str(additional))
            additional += 1

    logging.basicConfig(filename=logging_file, level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')

    gid = args.gname
    try:
        gid = getgrnam(gid)
        user_ids = [getpwnam(user_name).pw_uid for user_name in gid.gr_mem]
        if not user_ids:
            logging.info("The given group has no users. Exiting, because there are no files that could be saved.")
            sys.exit(1)

        base_dir = args.base_path
        if not exists(base_dir):
            logging.error("The given base directory does not exist. Please provide a valid path.")
            sys.exit(1)

        save_path = args.save_path
        if not exists(save_path):
            logging.error(
                "The given saving directory does not exist. Please provide a valid path.")
            sys.exit(1)

        compression_mode = "w:gz" if not args.no_compression else "w"

        if current_time_stamp is None:
            current_time_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        tar_archive_name = current_time_stamp + "_" + args.gname + "-" + \
                   base_dir[1:].replace("/", "_")
        tar_archive_number = 0
        while exists(join(save_path, tar_archive_name + f"{tar_archive_number if tar_archive_number > 0 else ''}.tar{'.gz' if not args.no_compression else ''}")):
            tar_archive_number += 1
        tar_archive_name = tar_archive_name + f"{tar_archive_number if tar_archive_number > 0 else ''}.tar{'.gz' if not args.no_compression else ''}"
        logging.info("----- Starting gathering all relevant files and directories -----")
        start_time = datetime.now()
        file_collector = FileCollector(user_ids, base_dir, logging)
        logging.info(f"Collecting of all elements took {datetime.now() - start_time} (h:m:s.ms)")
        logging.info("----- Gathering finished successfully -----")

        logging.info("----- Starting archiving the found files -----")
        start_time = datetime.now()
        file_collector.create_archive(save_path, tar_archive_name, compression_mode)
        logging.info(f"Archiving of all files took {datetime.now() - start_time} (h:m:s.ms)")
        logging.info("----- Archiving finished successfully -----")
    except KeyError:
        logging.error("The given group name was invalid. Please provide a valid group name")
