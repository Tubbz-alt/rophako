# -*- coding: utf-8 -*-

"""Endpoints for contacting the site owner."""

from flask import Blueprint, g, request, redirect, url_for, session, flash
import re
import time

from rophako.utils import template, send_email
from rophako.log import logger
from config import *

mod = Blueprint("contact", __name__, url_prefix="/contact")


@mod.route("/")
def index():
    return template("contact/index.html")


@mod.route("/send", methods=["POST"])
def send():
    """Submitting the contact form."""
    name    = request.form.get("name", "") or "Anonymous"
    email   = request.form.get("email", "")
    subject = request.form.get("subject", "") or "[No Subject]"
    message = request.form.get("message", "")

    # Spam traps.
    trap1 = request.form.get("contact", "x") != ""
    trap2 = request.form.get("website", "x") != "http://"
    if trap1 or trap2:
        flash("Wanna try that again?")
        return redirect(url_for(".index"))

    # Message is required.
    if len(message) == 0:
        flash("The message is required.")
        return redirect(url_for(".index"))

    # Send the e-mail.
    send_email(
        to=NOTIFY_ADDRESS,
        subject="Contact Form on {}: {}".format(SITE_NAME, subject),
        message="""A visitor to {site_name} has sent you a message!

IP Address: {ip}
User Agent: {ua}
Referrer: {referer}
Name: {name}
E-mail: {email}
Subject: {subject}

{message}""".format(
            site_name=SITE_NAME,
            ip=request.remote_addr,
            ua=request.user_agent.string,
            referer=request.headers.get("Referer", ""),
            name=name,
            email=email,
            subject=subject,
            message=message,
        )
    )

    flash("Your message has been delivered.")
    return redirect(url_for("index"))