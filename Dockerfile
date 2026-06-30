ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}

ARG APP_WORKDIR

WORKDIR ${APP_WORKDIR}

ARG STREAMLIT_SERVER_PORT

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE ${STREAMLIT_SERVER_PORT}

CMD ["streamlit", "run", "app.py"]
