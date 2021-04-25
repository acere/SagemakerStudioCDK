import logging
import os
import shutil
import traceback
from pathlib import Path

import boto3
from git import Repo

smclient = boto3.client("sagemaker")


def on_event(event, context):
    request_type = event["RequestType"]
    if request_type == "Create":
        return on_create(event)
    if request_type == "Update":
        return on_update(event)
    if request_type == "Delete":
        return on_delete(event)
    raise Exception(f"Invalid request type: {request_type}")


def on_create(event):
    props = event["ResourceProperties"]

    git_repo = props["GitRepository"]
    user_profile_name = props["StudioUserName"]
    domain_id = props["DomainID"]

    response = smclient.describe_user_profile(
        DomainId=domain_id, UserProfileName=user_profile_name
    )

    # Extract the user UID for setting files ownership
    efs_uid = int(response["HomeEfsFileSystemUid"])
    home_folder = Path(f"/mnt/efs/{efs_uid}")

    try:
        # The root of the EFS contains folders named for each user UID, but these may not be created before
        # the user has first logged in (could os.listdir("/mnt/efs") to check):
        print("Creating/checking home folder...")
        home_folder.mkdir(exist_ok=True)

        # Now ready to clone in Git content (or whatever else...)
        print(f"Cloning repo... {git_repo}")

        # Our target folder for Repo.clone_from() needs to be the *actual* target folder, not the parent
        # under which a new folder will be created, so we'll infer that from the repo name:
        repo_folder_name = git_repo.rpartition("/")[2]
        if repo_folder_name.lower().endswith(".git"):
            repo_folder = home_folder / repo_folder_name[: -len(".git")]

        shutil.rmtree(repo_folder, ignore_errors=True)

        Repo.clone_from(url=git_repo, to_path=repo_folder)
        # Set ownership/permissions for all the stuff just created, to give the user write
        # access:
        os.chown(repo_folder, uid=efs_uid, gid=-1)
        [os.chown(p, uid=efs_uid, gid=-1) for p in repo_folder.rglob("*")]

    except Exception as e:
        # Don't bring the entire CF stack down just because we couldn't copy a repo:
        traceback.print_exc()

    print("All done")

    logging.info("**SageMaker Studio user '%s' set up successfully", user_profile_name)
    physical_id = f'user_{efs_uid}'
    return {'PhysicalResourceId': physical_id }


def on_delete(event):
    physical_id = event["PhysicalResourceId"]
    props = event["ResourceProperties"]
    user_profile_name = props["StudioUserName"]
    domain_id = props["DomainID"]

    logging.info("**Received delete event")
    logging.info(
        f"**Deleting user setup is a no-op: user {user_profile_name} on domain {domain_id}"
    )


def on_update(event):
    physical_id = event["PhysicalResourceId"]
    props = event["ResourceProperties"]
    logging.info("**Received update event")
    logging.info(
        "**Updating user setup is a no-op: user {user_profile_name} on domain {domain_id}",
    )
