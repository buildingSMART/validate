# API Quick Start


The preview of the Validation Service API is available at `https://dev.validate.buildingsmart.org/api`.

## Documentation

Auto-generated documentation is available in both
[Swagger](https://dev.validate.buildingsmart.org/api/swagger-ui) 
and
[Redocly](https://dev.validate.buildingsmart.org/api/redoc)
formats.

## Auth token

You will need an Authentication token before making calls to the API, 
which can be obtained by emailing [validate@buildingsmart.org](mailto:validate@buildingsmart.org).

You can use this token either as a Bearer token or use it as the password in combination with your username/email for basic authentication.

## Example usage

1. Sample to show difference between Token vs. Basic authentication

    ``` shell
     curl -X GET --location 'https://dev.validate.buildingsmart.org/api/validationrequest' --header 'Authorization: Token <TOKEN>'
    ```

    -or-

    ```shell
    curl -X GET --location 'https://dev.validate.buildingsmart.org/api/validationrequest' --header 'Authorization: Basic <HASH>'
    ```

    where `<HASH>` is the Base64-encoded email and token as password, separated by a colon, eg. base64(johndoe@gmail.com:abcdefgh12345)

2. Submit a POST request to the `/validationrequest` endpoint to initiate a new Validation Request (requires a file name and the file contents):

   ```shell
      curl -X POST --location 'https://dev.validate.buildingsmart.org/api/validationrequest' \

      --header 'Authorization: Token <TOKEN>' \

      --form 'file_name="valid_file.ifc"' \

      --form 'file=@"/.../buildingSMART/sample_files/valid_file.ifc"'
   ```

   It will return a JSON object that includes the id (public_id) you can use for future GET requests.

3. Fetch details of a single ValidationRequest via a GET request to the `/validationrequest` endpoint

   ```shell
      curl -X GET --location 'https://dev.validate.buildingsmart.org/api/validationrequest/r767775526' --header 'Authorization: Token <TOKEN>'
   ```

4. Fetch details of all ValidationRequests via a GET request to the `/validationrequest` endpoint

   ```shell
   curl -X GET --location 'https://dev.validate.buildingsmart.org/api/validationrequest' --header 'Authorization: Token <TOKEN>'
   ```

5. Fetch all ValidationTasks for two ValidationRequests via a GET request to the `/validationtask` endpoint

   ```shell
   curl -X GET --location 'https://dev.validate.buildingsmart.org/api/validationtask?request_public_id=r75257132,r383446691' --header 'Authorization: Token <TOKEN>'
   ```
   
6. Fetch all the outcomes of a single ValidationRequest via a GET request to the `/validationoutcome` endpoint

   ```shell
   curl -X GET --location 'https://dev.validate.buildingsmart.org/api/validationoutcome?request_public_id=r75257132' --header 'Authorization: Token <TOKEN>'
   ```
