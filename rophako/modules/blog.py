# -*- coding: utf-8 -*-

"""Endpoints for the web blog."""

from flask import Blueprint, g, request, redirect, url_for, session, flash
import re
import datetime
import calendar

import rophako.model.user as User
import rophako.model.blog as Blog
import rophako.model.comment as Comment
import rophako.model.emoticons as Emoticons
from rophako.utils import template, pretty_time, login_required
from rophako.log import logger
from config import *

mod = Blueprint("blog", __name__, url_prefix="/blog")

@mod.route("/")
def index():
    return template("blog/index.html")


@mod.route("/category/<category>")
def category(category):
    g.info["url_category"] = category
    return template("blog/index.html")


@mod.route("/entry/<fid>")
def entry(fid):
    """Endpoint to view a specific blog entry."""

    # Resolve the friendly ID to a real ID.
    post_id = Blog.resolve_id(fid)
    if not post_id:
        flash("That blog post wasn't found.")
        return redirect(url_for(".index"))

    # Look up the post.
    post = Blog.get_entry(post_id)
    post["post_id"] = post_id

    # Render emoticons.
    if post["emoticons"]:
        post["body"] = Emoticons.render(post["body"])

    # Get the author's information.
    post["profile"] = User.get_user(uid=post["author"])
    post["photo"]   = User.get_picture(uid=post["author"])
    post["photo_url"] = PHOTO_ROOT_PUBLIC

    # Pretty-print the time.
    post["pretty_time"] = pretty_time(BLOG_TIME_FORMAT, post["time"])

    # Count the comments for this post
    post["comment_count"] = Comment.count_comments("blog-{}".format(post_id))

    g.info["post"] = post
    return template("blog/entry.html")


@mod.route("/entry")
@mod.route("/index")
def dummy():
    return redirect(url_for(".index"))


@mod.route("/update", methods=["GET", "POST"])
@login_required
def update():
    """Post/edit a blog entry."""

    # Get our available avatars.
    g.info["avatars"] = Blog.list_avatars()

    # Default vars.
    g.info.update(dict(
        post_id="",
        fid="",
        author=g.info["session"]["uid"],
        subject="",
        body="",
        avatar="",
        categories="",
        privacy=BLOG_DEFAULT_PRIVACY,
        emoticons=True,
        comments=BLOG_ALLOW_COMMENTS,
        month="",
        day="",
        year="",
        hour="",
        min="",
        sec="",
        preview=False,
    ))

    # Editing an existing post?
    post_id = request.args.get("id", None)
    if post_id:
        post_id = Blog.resolve_id(post_id)
        if post_id:
            logger.info("Editing existing blog post {}".format(post_id))
            post = Blog.get_entry(post_id)
            g.info["post_id"] = post_id
            g.info["post"] = post

            # Copy fields.
            for field in ["author", "fid", "subject", "body", "avatar",
                          "categories", "privacy", "emoticons", "comments"]:
                g.info[field] = post[field]

            # Dissect the time.
            date = datetime.datetime.fromtimestamp(post["time"])
            g.info.update(dict(
                month="{:02d}".format(date.month),
                day="{:02d}".format(date.day),
                year=date.year,
                hour="{:02d}".format(date.hour),
                min="{:02d}".format(date.minute),
                sec="{:02d}".format(date.second),
            ))

    # Are we SUBMITTING the form?
    if request.method == "POST":
        action = request.form.get("action")

        # Get all the fields from the posted params.
        g.info["post_id"] = request.form.get("id")
        for field in ["fid", "subject", "body", "avatar", "categories", "privacy"]:
            g.info[field] = request.form.get(field)
        for boolean in ["emoticons", "comments"]:
            print "BOOL:", boolean, request.form.get(boolean)
            g.info[boolean] = True if request.form.get(boolean, None) == "true" else False
            print g.info[boolean]
        for number in ["author", "month", "day", "year", "hour", "min", "sec"]:
            g.info[number] = int(request.form.get(number, 0))

        # What action are they doing?
        if action == "preview":
            g.info["preview"] = True
        elif action == "publish":
            # Publishing! Validate inputs first.
            invalid = False
            if len(g.info["body"]) == 0:
                invalid = True
                flash("You must enter a body for your blog post.")
            if len(g.info["subject"]) == 0:
                invalid = True
                flash("You must enter a subject for your blog post.")

            # Make sure the times are valid.
            date = None
            try:
                date = datetime.datetime(
                    g.info["year"],
                    g.info["month"],
                    g.info["day"],
                    g.info["hour"],
                    g.info["min"],
                    g.info["sec"],
                )
            except ValueError, e:
                invalid = True
                flash("Invalid date/time: " + str(e))

            # Format the categories.
            tags = []
            for tag in g.info["categories"].split(","):
                tags.append(tag.strip())

            # Okay to update?
            if invalid is False:
                # Convert the date into a Unix time stamp.
                epoch = float(date.strftime("%s"))

                new_id, new_fid = Blog.post_entry(
                    post_id    = g.info["post_id"],
                    epoch      = epoch,
                    author     = g.info["author"],
                    subject    = g.info["subject"],
                    fid        = g.info["fid"],
                    avatar     = g.info["avatar"],
                    categories = tags,
                    privacy    = g.info["privacy"],
                    ip         = request.remote_addr,
                    emoticons  = g.info["emoticons"],
                    comments   = g.info["comments"],
                    body       = g.info["body"],
                )

                return redirect(url_for(".entry", fid=new_fid))


    if type(g.info["categories"]) is list:
        g.info["categories"] = ", ".join(g.info["categories"])

    return template("blog/update.html")


@mod.route("/delete", methods=["GET", "POST"])
@login_required
def delete():
    """Delete a blog post."""
    post_id = request.args.get("id")

    # Resolve the post ID.
    post_id = Blog.resolve_id(post_id)
    if not post_id:
        flash("That blog post wasn't found.")
        return redirect(url_for(".index"))

    if request.method == "POST":
        confirm = request.form.get("confirm")
        if confirm == "true":
            Blog.delete_entry(post_id)
            flash("The blog entry has been deleted.")
            return redirect(url_for(".index"))

    # Get the entry's subject.
    post = Blog.get_entry(post_id)
    g.info["subject"] = post["subject"]
    g.info["post_id"] = post_id

    return template("blog/delete.html")

def partial_index():
    """Partial template for including the index view of the blog."""

    # Get the blog index.
    index = Blog.get_index()
    pool  = {} # The set of blog posts to show.

    category = g.info.get("url_category", None)

    # Are we narrowing by category?
    if category:
        # Narrow down the index to just those that match the category.
        for post_id, data in index.iteritems():
            if not category in data["categories"]:
                continue
            pool[post_id] = data

        # No such category?
        if len(pool) == 0:
            flash("There are no posts with that category.")
            return redirect(url_for(".index"))
    else:
        pool = index

    # Separate the sticky posts from the normal ones.
    sticky, normal = set(), set()
    for post_id, data in pool.iteritems():
        if data["sticky"]:
            sticky.add(post_id)
        else:
            normal.add(post_id)

    # Sort the blog IDs by published time.
    posts = []
    posts.extend(sorted(sticky, key=lambda x: pool[x]["time"], reverse=True))
    posts.extend(sorted(normal, key=lambda x: pool[x]["time"], reverse=True))

    # Handle pagination.
    offset = request.args.get("skip", 0)
    try:    offset = int(offset)
    except: offset = 0

    # Handle the offsets, and get those for the "older" and "earlier" posts.
    # "earlier" posts count down (towards index 0), "older" counts up.
    g.info["offset"]  = offset
    g.info["earlier"] = offset - BLOG_ENTRIES_PER_PAGE if offset > 0 else 0
    g.info["older"]   = offset + BLOG_ENTRIES_PER_PAGE
    if g.info["earlier"] < 0:
        g.info["earlier"] = 0
    if g.info["older"] < 0 or g.info["older"] > len(posts):
        g.info["older"] = 0
    g.info["count"] = 0

    # Can we go to other pages?
    g.info["can_earlier"] = True if offset > 0 else False
    g.info["can_older"]   = False if g.info["older"] == 0 else True

    # Load the selected posts.
    selected = []
    stop = offset + BLOG_ENTRIES_PER_PAGE
    if stop > len(posts): stop = len(posts)
    for i in range(offset, stop):
        post_id = posts[i]
        post    = Blog.get_entry(post_id)

        post["post_id"] = post_id

        # Render emoticons.
        if post["emoticons"]:
            post["body"] = Emoticons.render(post["body"])

        # Get the author's information.
        post["profile"] = User.get_user(uid=post["author"])
        post["photo"]   = User.get_picture(uid=post["author"])
        post["photo_url"] = PHOTO_ROOT_PUBLIC

        post["pretty_time"] = pretty_time(BLOG_TIME_FORMAT, post["time"])

        # Count the comments for this post
        post["comment_count"] = Comment.count_comments("blog-{}".format(post_id))

        selected.append(post)
        g.info["count"] += 1

    g.info["category"] = category
    g.info["posts"] = selected

    return template("blog/index.inc.html")