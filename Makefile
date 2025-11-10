#!/usr/bin/make

export PYTHONPATH=:$(PWD)/apps

run:
	uvicorn core.asgi:application --host 0.0.0.0 --port 8000 --reload

migrate:
	python manage.py migrate

makemigrations:
	python manage.py makemigrations

createsuperuser:
	python manage.py createsuperuser

shell:
	python manage.py shell

dbshell:
	python manage.py dbshell
