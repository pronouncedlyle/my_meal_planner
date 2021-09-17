import os
import string
import re

from cs50 import SQL
import sqlite3
from flask import Flask, flash, jsonify, redirect, render_template, request, session
#from flask_session import Session
from tempfile import mkdtemp
from functools import wraps
#import requests
import urllib.parse
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from my_meal_planner import app

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
#app.config["SESSION_FILE_DIR"] = mkdtemp()
#app.config["SESSION_PERMANENT"] = False
#app.config["SESSION_TYPE"] = "filesystem"
#Session(app)

# Configure CS50 Library to use SQLite database
#db = SQL("my_meal_planner\local_database\mealPlanner.db")

connection = sqlite3.connect("mealPlanner.db")

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/index")
        return f(*args, **kwargs)
    return decorated_function

@app.route("/myMeals", methods=["GET", "POST"])
@login_required
def myMeals():

    if request.method == "POST":

        myMeals = db.execute("SELECT * FROM meals WHERE user_id = :user_id ORDER BY meal_name COLLATE NOCASE;",
                             user_id = session["user_id"])

        # declare list for printing to shoppingList
        shoppingList = []
        finalShoppingList = []

        for row in myMeals:

            # counts how many times the meal has been selected for the week
            # this should probably be cleaned up and put into a function...
            count = 0

            if request.form.getlist("M" + str(row["meal_name"])):
                count += 1

            if request.form.getlist("T" + str(row["meal_name"])):
                count += 1

            if request.form.getlist("W" + str(row["meal_name"])):
                count += 1

            if request.form.getlist("Th" + str(row["meal_name"])):
                count += 1

            if request.form.getlist("F" + str(row["meal_name"])):
                count += 1

            if request.form.getlist("S" + str(row["meal_name"])):
                count += 1

            if request.form.getlist("Su" + str(row["meal_name"])):
                count += 1

            # query db for all ingredients in that meal
            if count > 0:
                ingredientList = db.execute("SELECT * FROM ingredients WHERE meal_id = :meal_id ORDER BY ingredient COLLATE NOCASE;",
                                         meal_id = row["meal_id"])

                # write ingredient info to dictionary in shoppingList
                for row in ingredientList:
                    shoppingList.append({"Ingredient": row["ingredient"] , "Quantity": row["quantity"] , "Unit": row["unit"]})

        # catches if user didn't check any boxes
        if shoppingList == []:
            flash("Please select a meal for at least one day to generate a shopping list.")
            return redirect ("/myMeals")

        #function to check for duplicates in list, then merge them (as long as units are the same)
        for i in range(len(shoppingList)):
            for j in range((i+1), len(shoppingList)):
                if shoppingList[j]["Ingredient"].lower() == shoppingList[i]["Ingredient"].lower() and shoppingList[j]["Unit"] == shoppingList[i]["Unit"]:
                    # add quantities
                    shoppingList[i]["Quantity"] += shoppingList[j]["Quantity"]
                    shoppingList[j]["Quantity"] = 0

        # remove old duplicate ingredient entries by making new list
        for i in range(len(shoppingList)):
            if shoppingList[i]["Quantity"] != 0:
                finalShoppingList.append(shoppingList[i])

        return render_template("shoppingList.html", myMeals=myMeals, finalShoppingList=finalShoppingList)


    else:

        # variable to detect if user has any meals in database
        empty = False

        myMeals = db.execute("SELECT * FROM meals WHERE user_id = :user_id ORDER BY meal_name COLLATE NOCASE;",
                             user_id = session["user_id"])

        # this query was for the modal to populate ingredients for each meal. Add this feature later
        #ingredients = db.execute("SELECT * FROM ingredients JOIN meals ON meals.meal_id = ingredients.meal_id WHERE user_id = :user_id ORDER BY ingredient COLLATE NOCASE;",
                                 #user_id = session["user_id"])

        if len(myMeals) == 0:
            empty = True

        return render_template("myMeals.html", myMeals=myMeals, empty=empty)


@app.route("/addMeal", methods=["GET", "POST"])
@login_required
def addMeal():

    if request.method == "POST":

        # Check for correct inputs
        if not request.form.get("meal_name"):
            flash("Please provide a name for your meal.")
            return redirect("/addMeal")

        elif not request.form.get("ingredient_0"):
            flash("Please provide at least one ingredient for your meal")
            return redirect("/addMeal")

        # Check that inputs are OK
        for i in range(0, 10):
            # check if row is occupied
            if not request.form.get("ingredient_" + str(i)):
                continue

            # check that row is complete
            if not request.form.get("quantity_" + str(i)):
                flash("Please input quantity for all ingredients")
                return redirect("/addMeal")

        # add meal
        db.execute("INSERT INTO meals (user_id, meal_name) VALUES (:user_id, :meal_name);",
                    user_id = session["user_id"],
                    meal_name = request.form.get("meal_name"),
                    )

        # query so I can get meal_id to write to ingredients table
        rows = db.execute("SELECT * FROM meals WHERE meal_name = :meal_name;",
                  meal_name = request.form.get("meal_name"),
                  )

        for i in range(0, 10):
            # check if row is occupied
            if not request.form.get("ingredient_" + str(i)):
                continue

            # add ingredient
            db.execute("INSERT INTO ingredients (meal_id, ingredient, quantity, unit) \
                        VALUES (:meal_id, :ingredient, :quantity, :unit);",
                        meal_id = rows[0]["meal_id"],
                        ingredient = request.form.get("ingredient_" + str(i)),
                        quantity = request.form.get("quantity_" + str(i)),
                        unit = request.form.get("unit_" + str(i)),
                        )

        return redirect("/myMeals")


    else:

        return render_template("addMeal.html")


@app.route("/deleteMeal", methods=["GET", "POST"])
@login_required
def deleteMeal():

    # DELETES MEAL AND INGREDIENTS
    if request.method == "POST":

        meal_id = request.form["deleteMeal"]

        # get meal_id
        rows = db.execute("SELECT * FROM meals WHERE meal_id = :meal_id",
                          meal_id = meal_id )

        # delete ingredients with that id
        db.execute("DELETE FROM ingredients WHERE meal_id = :meal_id;",
                    meal_id = rows[0]["meal_id"] )

        # delete meal
        db.execute("DELETE FROM meals WHERE meal_id = :meal_id;",
                   meal_id = rows[0]["meal_id"] )

        return redirect("/myMeals")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash('Please provide a username')
            return redirect("/register")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash('Please provide a password')
            return redirect("/register")

        # Ensure username conditions are met.
        regex = re.compile('[@_!#$%^&*() <>?/\|}{~:]')
        if len(request.form.get("username")) > 15 or (regex.search(request.form.get("username")) != None):
            flash('Username must be less than 15 characters and cannot contain special characters.')
            return redirect("/register")

        # Does username already exist?
        rows = db.execute("SELECT * FROM users WHERE username = :username;",
                          username=request.form.get("username"))
        if len(rows) != 0:
            flash('Username already exists!')
            return redirect("/register")

        # Ensure password conditions are met
        if len(request.form.get("password")) < 7 or len(request.form.get("password")) > 20:
            flash('Password must be at least 7 characters and no more than 20')
            return redirect("/register")

        # Ensure password matches confirmation
        if (request.form.get("password")) != (request.form.get("passwordConfirm")):
            flash('Password and confirmation must match')
            return redirect("/register")

        # Add username & password to db
        db.execute("INSERT INTO users(username, hash) VALUES (:username, :hash);",
                    username=request.form.get("username"),
                    hash=generate_password_hash(request.form.get("password")))

        rows = db.execute("SELECT * FROM users WHERE username = :username;",
                          username=request.form.get("username"))

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to myMeals page
        return redirect("/myMeals")

    # when requested via GET, should display registration form
    else:
        return render_template("register.html")


@app.route('/')
@app.route("/index", methods=["GET", "POST"]) # this function is done, use it as a guide
def index():
    """Log user in"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash('Please provide your username')
            return redirect("/index")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash('Please provide password')
            return redirect("/index")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username;",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash('Invalid username and/or password.')
            return redirect("/index")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]

        # Redirect user to myMeals page
        return redirect("/myMeals")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("index.html")

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/index")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return redirect("/myMeals")


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)