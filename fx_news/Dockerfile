FROM python 3.10.12

# Create the home directory and add files to it
WORKDIR /workspace
ADD . /workspace

RUN pip install -r requirements.txt

# Define your default launching command to start the application:
CMD [ "streamlit" . "run" "/workspace/fx_monitor_news_dark.py". "--server.address=0.0.0.0" ]

# Give correct access rights to ovhcloud user (42420:42420):
RUN chown -R 42420.42420 /workspace
ENV HOME=/workspace