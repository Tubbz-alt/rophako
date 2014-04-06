# -*- coding: utf-8 -*-

"""Blog models."""

from flask import g
import time
import re
import glob

import config
import rophako.jsondb as JsonDB
from rophako.log import logger

def get_index():
    """Get the blog index.

    The index is the cache of available blog posts. It has the format:

    ```
    {
        'post_id': {
            fid: Friendly ID for the blog post (for URLs)
            time: epoch time of the post
            sticky: the stickiness of the post (shows first on global views)
            author: the author user ID of the post
            categories: [ list of categories ]
            privacy: the privacy setting
            subject: the post subject
        },
        ...
    }
    ```
    """

    # Index doesn't exist?
    if not JsonDB.exists("blog/index"):
        return {}
    db = JsonDB.get("blog/index")

    # Hide any private posts if we aren't logged in.
    if not g.info["session"]["login"]:
        for post_id, data in db.iteritems():
            if data["privacy"] == "private":
                del db[post_id]

    return db


def __get_categories():
    """Get the blog categories cache.

    The category cache is in the following format:

    ```
    {
        'category_name': {
            'post_id': 'friendly_id',
            ...
        },
        ...
    }
    ```
    """

    # Index doesn't exist?
    if not JsonDB.exists("blog/tags"):
        return {}
    return JsonDB.get("blog/tags")


def get_entry(post_id):
    """Load a full blog entry."""
    if not JsonDB.exists("blog/entries/{}".format(post_id)):
        return None

    db = JsonDB.get("blog/entries/{}".format(post_id))

    # If no FID, set it to the ID.
    if len(db["fid"]) == 0:
        db["fid"] = str(post_id)

    return db


def post_entry(post_id, fid, epoch, author, subject, avatar, categories,
               privacy, ip, emoticons, comments, body):
    """Post (or update) a blog entry."""

    # Fetch the index.
    index = get_index()

    # Editing an existing post?
    if not post_id:
        post_id = get_next_id(index)

    logger.debug("Posting blog post ID {}".format(post_id))

    # Get a unique friendly ID.
    if not fid:
        # The default friendly ID = the subject.
        fid = subject.lower()
        fid = re.sub(r'[^A-Za-z0-9]', '-', fid)
        fid = re.sub(r'\-+', '-', fid)
        fid = fid.strip("-")
        logger.debug("Chosen friendly ID: {}".format(fid))

    # Make sure the friendly ID is unique!
    if len(fid):
        test = fid
        loop = 1
        logger.debug("Verifying the friendly ID is unique: {}".format(fid))
        while True:
            collision = False

            for k, v in index.iteritems():
                # Skip the same post, for updates.
                if k == post_id: continue

                if v["fid"] == test:
                    # Not unique.
                    loop += 1
                    test = fid + "_" + unicode(loop)
                    collision = True
                    logger.debug("Collision with existing post {}: {}".format(k, v["fid"]))
                    break

            # Was there a collision?
            if collision:
                continue # Try again.

            # Nope!
            break
        fid = test

    # Write the post.
    JsonDB.commit("blog/entries/{}".format(post_id), dict(
        fid        = fid,
        ip         = ip,
        time       = epoch or int(time.time()),
        categories = categories,
        sticky     = False, # TODO: implement sticky
        comments   = comments,
        emoticons  = emoticons,
        avatar     = avatar,
        privacy    = privacy or "public",
        author     = author,
        subject    = subject,
        body       = body,
    ))

    # Update the index cache.
    index[post_id] = dict(
        fid        = fid,
        time       = epoch or int(time.time()),
        categories = categories,
        sticky     = False, # TODO
        author     = author,
        privacy    = privacy or "public",
        subject    = subject,
    )
    JsonDB.commit("blog/index", index)

    return post_id, fid


def delete_entry(post_id):
    """Remove a blog entry."""
    # Fetch the blog information.
    index = get_index()
    post  = get_entry(post_id)
    if post is None:
        logger.warning("Can't delete post {}, it doesn't exist!".format(post_id))

    # Delete the post.
    JsonDB.delete("blog/entries/{}".format(post_id))

    # Update the index cache.
    del index[str(post_id)] # Python JSON dict keys must be strings, never ints
    JsonDB.commit("blog/index", index)


def resolve_id(fid):
    """Resolve a friendly ID to the blog ID number."""
    index = get_index()

    # If the ID is all numeric, it's the blog post ID directly.
    if re.match(r'^\d+$', fid):
        if fid in index:
            return int(fid)
        else:
            logger.error("Tried resolving blog post ID {} as an EntryID, but it wasn't there!".format(fid))
            return None

    # It's a friendly ID. Scan for it.
    for post_id, data in index.iteritems():
        if data["fid"] == fid:
            return int(post_id)

    logger.error("Friendly post ID {} wasn't found!".format(fid))
    return None


def list_avatars():
    """Get a list of all the available blog avatars."""
    avatars = set()
    paths = [
        # Load avatars from both locations. We check the built-in set first,
        # so if you have matching names in your local site those will override.
        "rophako/www/static/avatars/*.*",
        "site/www/static/avatars/*.*",
    ]
    for path in paths:
        for filename in glob.glob(path):
            filename = filename.split("/")[-1]
            avatars.add(filename)

    return sorted(avatars, key=lambda x: x.lower())


def get_next_id(index):
    """Get the next free ID for a blog post."""
    logger.debug("Getting next available blog ID number")
    sort = sorted(index.keys(), key=lambda x: int(x))
    logger.debug("Highest post ID is: {}".format(sort[-1]))
    next_id = int(sort[-1]) + 1

    # Sanity check!
    if next_id in index:
        raise Exception("Failed to get_next_id for the blog. Chosen ID is still in the index!")
    return next_id