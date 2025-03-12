# electro - bot's development made easy

A framework for building bots, made for humans.


# How to run?
1. Install the `poetry` environment:
   ```shell
   poetry install
   ```

2. Go to the `./examples` directory:
    ```shell
    cd ./examples
    ```

3. Make sure you have all the required configs in `.env` file:
    ```shell
    cp .env.example .env
    # vi .env

4. Extract and compile translations:
    ```shell
    make upload-locales
    make update-locales
    ```

5. Run the `TestFlow`:
   ```shell
   poetry run python ./test_flow.py
   ```

6. Check the API server @ http://localhost:8000/docs.
7. Use one of the clients to connect the platforms: [Discord](https://github.com/CyberCRI/ikigai-discord-client).