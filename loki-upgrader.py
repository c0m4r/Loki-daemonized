#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Loki upgrader

Loki - Simple IOC Scanner Copyright (c) 2015 Florian Roth
Loki (daemonized) - Simple IOC and YARA Scanner fork (c) 2023 c0m4r

https://github.com/c0m4r/Loki-daemonized

Licensed under GPL 3.0
"""
import argparse
import os
import platform
import sys
from io import BytesIO
from os.path import exists
from traceback import print_exc as trace
from typing import Any
from urllib.parse import urlparse
from shutil import copyfileobj
from signal import signal, SIGPIPE, SIG_DFL
from zipfile import ZipFile

# Modules
import requests
from colorama import Fore, Style

signal(SIGPIPE, SIG_DFL)

# System
SYSTEM = platform.system()

# Arch
ARCH = platform.machine()


def color_chooser(log_type: str) -> str:
    """
    Color selection
    """
    if log_type == "DEBUG":
        color = Fore.MAGENTA
    elif log_type == "ERROR":
        color = Fore.RED
    elif log_type == "INFO":
        color = Fore.CYAN
    else:
        color = ""

    return color


def log(log_type: str, module: str, message: str) -> None:
    """
    Logger
    """
    log_type_colored = color_chooser(log_type) + log_type + Style.RESET_ALL

    print(f"[ {log_type_colored} ]", f"{module}:", message)


def needs_update(sig_url: str) -> bool:
    """
    Check if Loki needs update
    """
    try:
        o = urlparse(sig_url)
        path = o.path.split("/")
        branch = path[4].split(".")[0]
        path.pop(len(path) - 1)
        path.pop(len(path) - 1)
        url = (
            o.scheme
            + "://api."
            + o.netloc
            + "/repos"
            + "/".join(path)
            + "/commits/"
            + branch
        )
        response_info = requests.get(url=url, timeout=5)
        j = response_info.json()
        sha = j["sha"]
        cache = "_".join(path) + ".cache"
        changed = False
        if exists(cache):
            with open(cache, "r", encoding="utf-8") as file:
                old_sha = file.read().rstrip()
            if sha != old_sha:
                changed = True
        else:
            with open(cache, "w", encoding="utf-8") as file:
                file.write(sha)
                changed = True
        return changed
    except Exception:
        return True


class LOKIUpdater:
    """
    Loki updater
    """

    UPDATE_URL_SIGS: list[str] = [
        "https://github.com/Neo23x0/signature-base/archive/master.zip",
        "https://github.com/reversinglabs/reversinglabs-yara-rules/archive/develop.zip",
    ]

    UPDATE_URL_LOKI: str = (
        "https://api.github.com/repos/c0m4r/Loki-daemonized/releases/latest"
    )

    def __init__(
        self,
        debug: bool,
        application_path: str,
    ) -> None:
        self.debug = debug
        self.application_path = application_path

    def make_sigdirs(self, sig_dir: str) -> None:
        """
        Make signatures dirs
        """
        for out_dir in ["", "iocs", "yara", "misc"]:
            full_out_dir = os.path.join(sig_dir, out_dir)
            if not os.path.exists(full_out_dir):
                os.makedirs(full_out_dir)
                log("DEBUG", "makedir", full_out_dir)

    def get_target_file(self, zip_file_path: str, sig_dir: str, sig_name: str) -> str:
        """
        Get target file
        """
        if "/iocs/" in zip_file_path and zip_file_path.endswith(".txt"):
            target_file = os.path.join(sig_dir, "iocs", sig_name)
        elif "/yara/" in zip_file_path and zip_file_path.endswith(".yar"):
            target_file = os.path.join(sig_dir, "yara", sig_name)
        elif "/misc/" in zip_file_path and zip_file_path.endswith(".txt"):
            target_file = os.path.join(sig_dir, "misc", sig_name)
        elif zip_file_path.endswith(".yara"):
            target_file = os.path.join(sig_dir, "yara", sig_name)
        else:
            target_file = ""
        return target_file

    def get_response(self, sig_url: str) -> Any:
        """
        Get response from signature URL
        """
        # Downloading current repository
        try:
            log("INFO", "Upgrader", f"Downloading {sig_url} ...")
            return requests.get(url=sig_url, timeout=5)
        except Exception:
            if self.debug:
                trace()
            log(
                "ERROR",
                "Upgrader",
                "Error downloading the signature database "
                "- check your Internet connection",
            )
            sys.exit(1)
        return ""

    def update_signatures_base(self, force: bool, debug: bool, sig_url: str) -> None:
        """
        Update signature rules
        """
        # Downloading current repository
        response = self.get_response(sig_url)

        # Preparations
        try:
            sig_dir = os.path.join(
                self.application_path, os.path.abspath("signature-base/")
            )
            self.make_sigdirs(sig_dir)
        except Exception:
            if self.debug:
                trace()
            log(
                "ERROR",
                "Upgrader",
                "Error while creating the signature-base directories",
            )
            sys.exit(1)

        # Read ZIP file
        try:
            zip_update = ZipFile(BytesIO(response.content))
            for zip_file_path in zip_update.namelist():
                sig_name = os.path.basename(zip_file_path)
                if zip_file_path.endswith("/"):
                    continue

                # Extract the rules
                if debug:
                    log(
                        "DEBUG",
                        "Upgrader",
                        f"Extracting {zip_file_path} ...",
                    )

                target_file = self.get_target_file(zip_file_path, sig_dir, sig_name)

                if not target_file:
                    continue

                # New file
                if not os.path.exists(target_file):
                    log(
                        "INFO",
                        "Upgrader",
                        f"New signature file: {sig_name}",
                    )

                # Extract file
                source = zip_update.open(zip_file_path)
                target = open(target_file, "wb")
                with source, target:
                    copyfileobj(source, target)
                target.close()
                source.close()

        except Exception:
            if self.debug:
                trace()
            log(
                "ERROR",
                "Upgrader",
                "Error while extracting the signature files from the download package",
            )
            sys.exit(1)

    def update_signatures(self, force: bool, debug: bool) -> None:
        """
        Update signatures
        """
        for sig_url in self.UPDATE_URL_SIGS:
            if needs_update(sig_url) or force:
                try:
                    self.update_signatures_base(force, debug, sig_url)
                except Exception:
                    if self.debug:
                        trace()
            else:
                log("INFO", "Upgrader", f"{sig_url} is up to date.")

    def get_loki_zip_file_url(self) -> str:
        """
        Get latest Loki zipfile download url from github api
        """
        response_info = requests.get(url=self.UPDATE_URL_LOKI, timeout=5)
        data = response_info.json()
        if "assets" in data:
            for asset in data["assets"]:
                zip_url = asset["browser_download_url"]
                if asset["browser_download_url"].endswith(f"{ARCH}.zip"):
                    return str(zip_url)
        elif "message" in data:
            log("ERROR", "GITHUB", data)
            sys.exit(1)
        return ""

    def update_loki(self) -> bool:
        """
        Update Loki
        """
        try:
            # Downloading the info for latest release
            try:
                log(
                    "INFO",
                    "Upgrader",
                    f"Checking location of latest release {self.UPDATE_URL_LOKI} ...",
                )
                # Get download URL
                zip_url = self.get_loki_zip_file_url()
                if zip_url:
                    log("INFO", "Upgrader", f"Downloading latest release {zip_url} ...")
                    response_zip = requests.get(url=zip_url, timeout=5)
                else:
                    log(
                        "ERROR",
                        "Upgrader",
                        "Error downloading the loki update - check your Internet connection",
                    )
                    sys.exit(1)
            except Exception:
                if self.debug:
                    trace()
                log(
                    "ERROR",
                    "Upgrader",
                    "Error downloading the loki update - check your Internet connection",
                )
                sys.exit(1)

            # Read ZIP file
            try:
                zip_update = ZipFile(BytesIO(response_zip.content))
                for zip_file_path in zip_update.namelist():
                    if zip_file_path.endswith("/") or "/config/" in zip_file_path:
                        continue

                    source = zip_update.open(zip_file_path)
                    target_file = "/".join(zip_file_path.split("/")[1:])

                    log("INFO", "Upgrader", f"Extracting {target_file} ...")

                    try:
                        # Create file if not present
                        if not os.path.exists(os.path.dirname(target_file)):
                            if os.path.dirname(target_file) != "":
                                os.makedirs(os.path.dirname(target_file))
                    except Exception:
                        if self.debug:
                            log(
                                "DEBUG",
                                "Upgrader",
                                f"Cannot create dir name '{os.path.dirname(target_file)}'",
                            )
                            trace()

                    try:
                        # Create target file
                        target = open(target_file, "wb")
                        with source, target:
                            copyfileobj(source, target)
                            if self.debug:
                                log(
                                    "DEBUG",
                                    "Upgrader",
                                    f"Successfully extracted '{target_file}'",
                                )
                        target.close()
                    except Exception:
                        log("ERROR", "Upgrader", f"Cannot extract '{target_file}'")
                        if self.debug:
                            trace()

            except Exception:
                if self.debug:
                    trace()
                log(
                    "ERROR",
                    "Upgrader",
                    "Error while extracting the signature files from the download package",
                )
                sys.exit(1)

        except Exception:
            if self.debug:
                trace()
            return False
        return True


def get_application_path() -> str:
    """
    Get application path
    """
    try:
        if getattr(sys, "frozen", False):
            application_path = os.path.dirname(os.path.realpath(sys.executable))
        else:
            application_path = os.path.dirname(os.path.realpath(__file__))
        return application_path
    except Exception:
        print("Error while evaluation of application path")
        trace()
        return ""


if __name__ == "__main__":
    # Parse Arguments
    parser = argparse.ArgumentParser(description="Loki - Upgrader")
    parser.add_argument(
        "--sigsonly",
        action="store_true",
        help="Update the signatures only",
        default=False,
    )
    parser.add_argument(
        "--progonly",
        action="store_true",
        help="Update the program files only",
        default=False,
    )
    parser.add_argument(
        "--debug", action="store_true", default=False, help="Debug output"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force signature update",
    )
    parser.add_argument(
        "--detached", action="store_true", default=False, help=argparse.SUPPRESS
    )

    args = parser.parse_args()

    # Update LOKI
    updater = LOKIUpdater(args.debug, get_application_path())

    if not args.sigsonly:
        log("INFO", "Upgrader", "Updating LOKI ...")
        updater.update_loki()
    if not args.progonly:
        log("INFO", "Upgrader", "Updating Signatures ...")
        updater.update_signatures(args.force, args.debug)

    log("INFO", "Upgrader", "Update complete")

    if args.detached:
        log("INFO", "Upgrader", "Press any key to return ...")

# EOF
