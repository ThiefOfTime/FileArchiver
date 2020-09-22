import logging
import shutil
import tarfile
import unittest

from grp import getgrnam
from os import chown, makedirs, mknod, remove, walk
from pwd import getpwall, getpwnam

from file_archiver import FileCollector


class TestFileArchiver(unittest.TestCase):

    def setUp(self) -> None:
        gid = getgrnam("sudo")
        self.users = getpwall()[:2]
        self.user_ids = [getpwnam("root").pw_uid] + [getpwnam(user_name).pw_uid for user_name in gid.gr_mem]
        self.create_test_dir()
        self.file_collector = FileCollector(self.user_ids, "/tmp/test", logging)
        self.file_collector.create_archive("/tmp", "test_tar_ball.tar.gz", "w:gz")
        self.extract_elements()
        self.number_of_dirs = 7
        self.number_of_files = 3
        self.number_of_dirs_complete = 8
        self.number_of_files_complete = 8

    def create_test_dir(self):
        # making dirs
        makedirs("/tmp/test/owned_by_user_1/owned_by_user_2")
        chown("/tmp/test", self.users[1].pw_uid, self.users[1].pw_gid)
        chown("/tmp/test/owned_by_user_1/owned_by_user_2", self.users[1].pw_uid, self.users[1].pw_gid)
        chown("/tmp/test/owned_by_user_1", self.users[0].pw_uid, self.users[0].pw_gid)
        makedirs("/tmp/test/owned_by_user_1/owned_by_user_1")
        chown("/tmp/test/owned_by_user_1/owned_by_user_1", self.users[0].pw_uid, self.users[0].pw_gid)
        makedirs("/tmp/test/owned_by_user_1/owned_by_user_1_empty")
        chown("/tmp/test/owned_by_user_1/owned_by_user_1_empty", self.users[0].pw_uid, self.users[0].pw_gid)
        makedirs("/tmp/test/owned_by_user_2/owned_by_user_1")
        chown("/tmp/test/owned_by_user_2", self.users[1].pw_uid, self.users[1].pw_gid)
        chown("/tmp/test/owned_by_user_2/owned_by_user_1", self.users[0].pw_uid, self.users[0].pw_gid)
        makedirs("/tmp/test/owned_by_user_2/owned_by_user_2")
        chown("/tmp/test/owned_by_user_2/owned_by_user_2", self.users[1].pw_uid, self.users[1].pw_gid)
        makedirs("/tmp/test/owned_by_user_2/owned_by_user_1_empty")
        chown("/tmp/test/owned_by_user_2/owned_by_user_1_empty", self.users[0].pw_uid, self.users[0].pw_gid)

        # making files
        mknod("/tmp/test/owned_by_user_1/file_user_1.txt")
        chown("/tmp/test/owned_by_user_1/file_user_1.txt", self.users[0].pw_uid, self.users[0].pw_gid)
        mknod("/tmp/test/owned_by_user_1/owned_by_user_2/file_user_1.txt")
        mknod("/tmp/test/owned_by_user_1/owned_by_user_2/file_user_2.txt")
        chown("/tmp/test/owned_by_user_1/owned_by_user_2/file_user_1.txt", self.users[0].pw_uid, self.users[0].pw_gid)
        chown("/tmp/test/owned_by_user_1/owned_by_user_2/file_user_2.txt", self.users[1].pw_uid, self.users[1].pw_gid)
        mknod("/tmp/test/owned_by_user_1/owned_by_user_1/file_user_1.txt")
        mknod("/tmp/test/owned_by_user_1/owned_by_user_1/file_user_2.txt")
        chown("/tmp/test/owned_by_user_1/owned_by_user_1/file_user_1.txt", self.users[0].pw_uid, self.users[0].pw_gid)
        chown("/tmp/test/owned_by_user_1/owned_by_user_1/file_user_2.txt", self.users[1].pw_uid, self.users[1].pw_gid)
        mknod("/tmp/test/owned_by_user_2/file_user_2.txt")
        chown("/tmp/test/owned_by_user_2/file_user_2.txt", self.users[1].pw_uid, self.users[1].pw_gid)
        mknod("/tmp/test/owned_by_user_2/owned_by_user_1/file_user_2.txt")
        mknod("/tmp/test/owned_by_user_2/owned_by_user_1/file_user_2.txt2")
        chown("/tmp/test/owned_by_user_2/owned_by_user_1/file_user_2.txt", self.users[1].pw_uid, self.users[1].pw_gid)
        chown("/tmp/test/owned_by_user_2/owned_by_user_1/file_user_2.txt2", self.users[1].pw_uid, self.users[1].pw_gid)

    def extract_elements(self):
        with tarfile.open("/tmp/test_tar_ball.tar.gz", "r:gz") as tarball:
            def change_base_path(tar_ball):
                for member in tar_ball.getmembers():
                    member.path = member.path.replace("test", "test2").split("/", maxsplit=1)[1]
                    yield member
            tarball.extractall("/tmp", members=change_base_path(tarball))

    def test_number_of_elements(self):
        num_files = 0
        num_dirs = 0
        for root, dirs, files in walk("/tmp/test2"):
            num_dirs += len(dirs)
            num_files += len(files)
        self.assertEqual(num_dirs, self.number_of_dirs)
        self.assertEqual(num_files, self.number_of_files)

    def test_archive_structure(self):
        first_iteration = True
        for (root1, dirs1, files1), (root2, dirs2, files2) in zip(walk("/tmp/test2"), walk("/tmp/test")):
            if not first_iteration:
                self.assertEqual(root1.split("/", maxsplit=3)[-1], root2.split("/", maxsplit=3)[-1])
            first_iteration = False
            self.assertTrue(set(dirs2).issuperset(dirs1))
            self.assertTrue(set(dirs2).issuperset(dirs1))

    def tearDown(self) -> None:
        shutil.rmtree("/tmp/test")
        remove("/tmp/test_tar_ball.tar.gz")
        shutil.rmtree("/tmp/test2")

