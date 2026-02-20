import { test, expect } from '@playwright/test';
import { readFileSync } from 'fs';
import { basename } from 'path';
import { statSync } from 'fs';
import { createAuthHeader, createFormData } from './utils.js';

const API_HOST_URL = process.env.API_HOST_URL ?? 'http://127.0.0.1:8000';
const API_BASE_URL = process.env.API_BASE_URL ?? API_HOST_URL + '/api';
const TEST_CREDENTIALS = 'root:root';

function findAndReadFileSync(filepath) {
    
    if (statSync(filepath, { throwIfNoEntry: false })?.isFile()) {
        return readFileSync(filepath);        
    } else if (statSync('e2e/' + filepath, { throwIfNoEntry: false })?.isFile()) {
        return readFileSync('e2e/' + filepath);
    }
    throw new Error(`File does not exist: ${filepath}`);
}

function createFormDataForTwoFiles(filePath1, filePath2) {

    const name1 = basename(filePath1);
    const file1 = new File([findAndReadFileSync(filePath1)], name1);
    const name2 = basename(filePath2);
    const file2 = new File([findAndReadFileSync(filePath2)], name2);

    const form = new FormData();
    form.append('file', file1);
    form.append('file_name', name1);
    form.append('file', file2);
    form.append('file_name', name2);
    return form;
}

function createDummyFormData(fileName, fileSize) {

    // create a buffer with zeros of specified size
    const largeBuffer = Buffer.alloc(fileSize, 0); 
    const file = new File([largeBuffer], fileName);
    const form = new FormData();
    form.append('file', file);
    form.append('file_name', fileName);
    return form;
}

test.describe('API - ValidationRequest', () => {

    const API_URL = `${API_BASE_URL}/v1/validationrequest`;

    test('POST accepts valid file', async ({ request }) => {

        // try to post a valid file
        const response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });

        // check if the response is correct - 201 Created
        expect(response.statusText()).toBe('Created');
        expect(response.status()).toBe(201);
    });

    test('POST with trailing slash accepts valid file', async ({ request }) => {

        // try to post a valid file
        const response = await request.post(`${API_URL}/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });

        // check if the response is correct - 201 Created
        expect(response.statusText()).toBe('Created');
        expect(response.status()).toBe(201);
    });

    test('POST implements file size limit', async ({ request }) => {

        // try to post a large file
        const response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createDummyFormData('very_large_file.ifc', 300 * 1024 * 1024) // 300 MB (> 256 MB limit)
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            file: [ 'File size exceeds allowed file size limit (256 MB).' ] 
        });
    });

    test('POST rejects empty request', async ({ request }) => {

        // try to post an empty request
        const response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 

        // check if the error details are correct
        expect(await response.json()).toEqual(
        {
            file: [ "No file was submitted." ], 
            file_name: [ "This field is required." ]
        });
    });

    test('POST rejects empty file', async ({ request }) => {

        // try to post an empty file
        const response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/empty_file.ifc')
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            file: [ 'The submitted file is empty.' ] 
        });
    });

    test('POST rejects empty file name', async ({ request }) => {

        // try to post a file with empty filename
        const response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc', '')
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 

        // check if the error details are correct
        expect(await response.json()).toStrictEqual(
        {
            file: [ "The submitted data was not a file. Check the encoding type on the form." ], 
            file_name: [ "This field is required." ]
        });
    });

    test('POST only accepts *.ifc files', async ({ request }) => {

        // try to post a file with invalid file extension
        const response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/invalid_file_extension')
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            file_name: [ "File name must end with '.ifc'." ] 
        });
    });

    test('POST only accepts a single file (for now)', async ({ request }) => {

        // try to post two valid files
        const response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormDataForTwoFiles(
                'fixtures/valid_file.ifc', 
                'fixtures/valid_file2.ifc'
            )
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            file: 'Only one file can be uploaded at a time.' 
        });
    });

    test('POST without authorization header returns 401', async ({ request }) => {

        // try to post a valid file but without authorization header
        const response = await request.post(`${API_URL}`, {
            multipart: createFormData('fixtures/valid_file.ifc')
        });

        // check if the response is correct - 401 Unauthorized
        expect(response.statusText()).toBe('Unauthorized');
        expect(response.status()).toBe(401);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Authentication credentials were not provided.'
        });
    });

    test('GET returns a single instance', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });
        const json_body = await response.json();
        const public_id = json_body['public_id'];

        // retrieve a single instance
        response = await request.get(`${API_URL}/${public_id}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(data).toHaveProperty('public_id');
        expect(data['public_id']).toBe(public_id);
    });

    test('GET with "public_id" query param returns a list with one instance', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });
        const json_body = await response.json();
        const public_id = json_body['public_id'];

        // retrieve a single instance by public id
        response = await request.get(`${API_URL}?public_id=${public_id}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(data).toHaveProperty('results');
        expect(Array.isArray(data.results)).toBe(true);
        expect(data.results.length).toBe(1);
        expect(data.results[0]).toHaveProperty('public_id');
        expect(data.results[0]['public_id']).toBe(public_id);
    });

    test('GET with trailing slash returns a single instance', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });
        const json_body = await response.json();
        const public_id = json_body['public_id'];

        // retrieve a single instance
        response = await request.get(`${API_URL}/${public_id}/`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(data).toHaveProperty('public_id');
        expect(data['public_id']).toBe(public_id);
    });

    test('GET with "public_id" query param returns a list with one object', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });
        const json_body = await response.json();
        const public_id = json_body['public_id'];
        const file_name = json_body['file_name']

        // retrieve a single instance
        response = await request.get(`${API_URL}?public_id=${public_id}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data.results.length).toBe(1);
        expect(data.results[0]).toHaveProperty('public_id');
        expect(data.results[0]['public_id']).toBe(public_id);
        expect(data.results[0]['file_name']).toBe(file_name);
        expect(data).toHaveProperty('metadata.result_set.total');
        expect(data).toHaveProperty('metadata.result_set.limit');
    });

    test('GET with "public_id" query param returns a list with multiple objects', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });
        const json_body = await response.json();
        const public_id = json_body['public_id'];

        // post a second valid file
        let response2 = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });
        const json_body2 = await response2.json();
        const public_id2 = json_body2['public_id'];

        // retrieve two instances
        response = await request.get(`${API_URL}?public_id=${public_id},${public_id2}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data.results.length).toBe(2);
    });

    test('GET returns a list', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });

        // retrieve list of ValidationRequests
        response = await request.get(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data.results.length).toBeGreaterThan(0);
        expect(data.results[0]).toHaveProperty('public_id');
        expect(data.results[0]).toHaveProperty('file_name');
        expect(data).toHaveProperty('metadata.result_set.total');
    });

    test('GET without trailing slash returns a list', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });

        // retrieve list of ValidationRequests
        response = await request.get(`${API_BASE_URL}/validationrequest`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data.results.length).toBe(25);
        expect(data.results[0]).toHaveProperty('public_id');
        expect(data).toHaveProperty('metadata.result_set.total');
        expect(data).toHaveProperty('metadata.result_set.limit');
    });

    test('GET without authorization header returns 401', async ({ request }) => {

        // try to retrieve a list
        const response = await request.get(`${API_URL}`);

        // check if the response is correct - 401 Unauthorized
        expect(response.statusText()).toBe('Unauthorized');
        expect(response.status()).toBe(401);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Authentication credentials were not provided.'
        });
    });

    test('GET with incorrect authorization header returns 401', async ({ request }) => {

        // try to retrieve a list
        const response = await request.get(`${API_URL}`, {
            headers: 'Authorization: Basic invalidcredentials'
        });

        // check if the response is correct - 401 Unauthorized
        expect(response.statusText()).toBe('Unauthorized');
        expect(response.status()).toBe(401);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Authentication credentials were not provided.'
        });
    });
    
    test('GET returns results ordered by "created" field', async ({ request }) => {

        // submit few valid files
        const NUM_REQUESTS = 3;
        for (let i = 0; i < NUM_REQUESTS; i++) {
            await request.post(`${API_URL}`, {
                headers: createAuthHeader(TEST_CREDENTIALS),
                multipart: createFormData('fixtures/valid_file.ifc', `valid_file_${NUM_REQUESTS}.ifc`)
            });
        }
        
        // retrieve list of ValidationRequests
        const res = await request.get(`${API_BASE_URL}/validationrequest`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        const data = await res.json();
      
        // check ordering - newest should be first
        const t0 = new Date(data.results[0].created).getTime();
        const t1 = new Date(data.results[1].created).getTime();
        const t2 = new Date(data.results[2].created).getTime();
        expect(t0).toBeGreaterThanOrEqual(t1);
        expect(t1).toBeGreaterThanOrEqual(t2);
    });

    test('GET should not return internal identifiers and fields', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });
        const json_body = await response.json();
        const public_id = json_body['public_id'];

        // retrieve a single instance
        response = await request.get(`${API_URL}/${public_id}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(data).toHaveProperty('public_id');
        expect(data).not.toHaveProperty('model');
        expect(data).not.toHaveProperty('model_id');
        expect(data).not.toHaveProperty('id');
        expect(data).not.toHaveProperty('deleted');
        expect(data).not.toHaveProperty('created_by');
        expect(data).not.toHaveProperty('updated_by');
        expect(data).not.toHaveProperty('status_reason');
    });

    test('DELETE should delete an instance', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });
        const json_body = await response.json();
        const public_id = json_body['public_id'];

        // delete the instance
        response = await request.delete(`${API_URL}/${public_id}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        expect(response.statusText()).toBe('No Content');
        expect(response.status()).toBe(204);

        // try to retrieve the instance that was just deleted
        response = await request.get(`${API_URL}${public_id}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 404 NOT FOUND
        expect(response.statusText()).toBe('Not Found');
        expect(response.status()).toBe(404);
    });

    test('DELETE should return 404 for non-existing instance', async ({ request }) => {

        const public_id = 'r000000000'; // assuming this ID does not exist
        
        // delete an instance
        let response = await request.delete(`${API_URL}/${public_id}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 404 NOT FOUND
        expect(response.statusText()).toBe('Not Found');
        expect(response.status()).toBe(404);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Validation Request with public_id=r000000000 does not exist.'
        });
    });

    test('DELETE without authorization header returns 401', async ({ request }) => {

        const public_id = 'r000000000'; // assuming this ID does not exist
         
        // try to delete an instance without authorization header
        const response = await request.delete(`${API_URL}/${public_id}`);

        // check if the response is correct - 401 Unauthorized
        expect(response.statusText()).toBe('Unauthorized');
        expect(response.status()).toBe(401);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Authentication credentials were not provided.'
        });
    });
});

test.describe('API - ValidationTask', () => {

    const API_URL = `${API_BASE_URL}/v1/validationtask`;

    test('GET returns a list', async ({ request }) => {

        // retrieve list of ValidationTasks
        const response = await request.get(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data.results.length).toBeGreaterThanOrEqual(0);
    });

    test('GET filtered by "request_public_id" returns a list', async ({ request }) => {

        // retrieve list of ValidationRequests
        let response = await request.get(`${API_BASE_URL}/validationrequest`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        let data = await response.json();
        const REQ_ID = data.results[0].public_id;

        // retrieve list of ValidationTasks filtered by request_public_id
        response = await request.get(`${API_URL}?request_public_id=${REQ_ID}`, { 
            headers: createAuthHeader(TEST_CREDENTIALS) 
        });

        // check if the response is correct - 200 OK
        expect(response.status()).toBe(200);
        data = await response.json();

        // check if the json body is correct
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data).toHaveProperty('metadata.result_set.total');
        for (const item of data.results) {
            expect(item).toHaveProperty('request');
            expect(item.request).toBe(REQ_ID);
        };        
    });

    test('GET respects limit query parameter', async ({ request }) => {

        // retrieve list of ValidationTasks with limit
        const LIMIT = 5;
        const response = await request.get(`${API_URL}/?limit=${LIMIT}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 200 OK
        expect(response.status()).toBe(200);
        const data = await response.json();

        // check if the json body is correct
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data).toHaveProperty('metadata.result_set.limit');
    
        // check if the limit is respected
        expect(data.results.length).toBeLessThanOrEqual(LIMIT);
        expect(data.metadata.result_set.limit).toBe(LIMIT);
    });

    test('GET without authorization header returns 401', async ({ request }) => {

        // try to retrieve a list of ValidationTasks
        const response = await request.get(`${API_URL}`);

        // check if the response is correct - 401 Unauthorized
        expect(response.statusText()).toBe('Unauthorized');
        expect(response.status()).toBe(401);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Authentication credentials were not provided.'
        });
    });

    test('POST should return 405 - Method Not Allowed', async ({ request }) => {

        // try to post a new ValidationTask
        const response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 405 Method Not Allowed
        expect(response.statusText()).toBe('Method Not Allowed');
        expect(response.status()).toBe(405);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Method "POST" not allowed.'
        });
    });

    test('PUT should return 405 - Method Not Allowed', async ({ request }) => {

        // try to update a ValidationTask
        const response = await request.put(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 405 Method Not Allowed
        expect(response.statusText()).toBe('Method Not Allowed');
        expect(response.status()).toBe(405);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Method "PUT" not allowed.'
        });
    });

    test('DELETE should return 405 - Method Not Allowed', async ({ request }) => {

        // try to delete a ValidationTask
        const response = await request.delete(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 405 Method Not Allowed
        expect(response.statusText()).toBe('Method Not Allowed');
        expect(response.status()).toBe(405);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Method "DELETE" not allowed.'
        });
    });
});

test.describe('API - ValidationOutcome', () => {

    const API_URL = `${API_BASE_URL}/v1/validationoutcome`;

    test('GET returns a list', async ({ request }) => {

        // retrieve list of ValidationOutcomes
        const response = await request.get(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data.results.length).toBeGreaterThanOrEqual(0);
    });

    test('GET filtered by "request_public_id" returns a list', async ({ request }) => {

        // retrieve list of ValidationRequests
        let response = await request.get(`${API_BASE_URL}/validationrequest`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        let data = await response.json();
        const REQ_ID = data.results[0].public_id;

        // retrieve list of ValidationOutcomes filtered by request_public_id
        response = await request.get(`${API_URL}?request_public_id=${REQ_ID}`, { 
            headers: createAuthHeader(TEST_CREDENTIALS) 
        });

        // check if the response is correct - 200 OK
        expect(response.status()).toBe(200);
        data = await response.json();

        // check if the json body is correct
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data).toHaveProperty('metadata.result_set.total');
        for (const item of data.results) {
            expect(item).toHaveProperty('request');
            expect(item.request).toBe(REQ_ID);
        };        
    });

    test('GET respects limit query parameter', async ({ request }) => {

        // retrieve list of ValidationOutcome with limit
        const LIMIT = 5;
        const response = await request.get(`${API_URL}/?limit=${LIMIT}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 200 OK
        expect(response.status()).toBe(200);
        const data = await response.json();

        // check if the json body is correct
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data).toHaveProperty('metadata.result_set.limit');
    
        // check if the limit is respected
        expect(data.results.length).toBeLessThanOrEqual(LIMIT);
        expect(data.metadata.result_set.limit).toBe(LIMIT);
    });

    test('GET without authorization header returns 401', async ({ request }) => {

        // try to retrieve a list of ValidationOutcomes
        const response = await request.get(`${API_URL}`);

        // check if the response is correct - 401 Unauthorized
        expect(response.statusText()).toBe('Unauthorized');
        expect(response.status()).toBe(401);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Authentication credentials were not provided.'
        });
    });

    test('POST should return 405 - Method Not Allowed', async ({ request }) => {

        // try to post a new ValidationOutcome
        const response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 405 Method Not Allowed
        expect(response.statusText()).toBe('Method Not Allowed');
        expect(response.status()).toBe(405);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Method "POST" not allowed.'
        });
    });

    test('PUT should return 405 - Method Not Allowed', async ({ request }) => {

        // try to update a ValidationOutcome
        const response = await request.put(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 405 Method Not Allowed
        expect(response.statusText()).toBe('Method Not Allowed');
        expect(response.status()).toBe(405);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Method "PUT" not allowed.'
        });
    });

    test('DELETE should return 405 - Method Not Allowed', async ({ request }) => {

        // try to delete a ValidationOutcome
        const response = await request.delete(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 405 Method Not Allowed
        expect(response.statusText()).toBe('Method Not Allowed');
        expect(response.status()).toBe(405);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Method "DELETE" not allowed.'
        });
    });
});

test.describe('API - Model', () => {

    const API_URL = `${API_BASE_URL}/v1/model`;

    test('GET returns a list', async ({ request }) => {

        // retrieve list of Models
        const response = await request.get(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data.results.length).toBeGreaterThanOrEqual(0);
    });

    test('GET filtered by "request_public_id" returns a list', async ({ request }) => {

        // submit a valid file
        const createRes = await request.post(`${API_BASE_URL}/v1/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });
        expect(createRes.status()).toBe(201);
        expect(createRes.ok()).toBeTruthy();
        const created = await createRes.json();
        const REQ_ID = created.public_id;

        // retrieve list of Models filtered by request_public_id
        const response = await request.get(`${API_URL}?request_public_id=${REQ_ID}`, { 
            headers: createAuthHeader(TEST_CREDENTIALS) 
        });

        // check if the response is correct - 200 OK
        expect(response.status()).toBe(200);
        const data = await response.json();

        // check if the json body is correct
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data).toHaveProperty('metadata.result_set.total');
        for (const item of data.results) {
            expect(item).toHaveProperty('request');
            expect(item.request).toBe(REQ_ID);
        };        
    });

    test('GET respects limit query parameter', async ({ request }) => {

        // retrieve list of ValidationOutcome with limit
        const LIMIT = 5;
        const response = await request.get(`${API_URL}?limit=${LIMIT}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 200 OK
        expect(response.status()).toBe(200);
        const data = await response.json();

        // check if the json body is correct
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data).toHaveProperty('metadata.result_set.limit');
    
        // check if the limit is respected
        expect(data.results.length).toBeLessThanOrEqual(LIMIT);
        expect(data.metadata.result_set.limit).toBe(LIMIT);
    });

    test('GET without authorization header returns 401', async ({ request }) => {

        // try to retrieve a list of Models
        const response = await request.get(`${API_URL}`);

        // check if the response is correct - 401 Unauthorized
        expect(response.statusText()).toBe('Unauthorized');
        expect(response.status()).toBe(401);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Authentication credentials were not provided.'
        });
    });

    test('POST should return 405 - Method Not Allowed', async ({ request }) => {

        // try to post a new Model
        const response = await request.post(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 405 Method Not Allowed
        expect(response.statusText()).toBe('Method Not Allowed');
        expect(response.status()).toBe(405);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Method "POST" not allowed.'
        });
    });

    test('PUT should return 405 - Method Not Allowed', async ({ request }) => {

        // try to update a Model
        const response = await request.put(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 405 Method Not Allowed
        expect(response.statusText()).toBe('Method Not Allowed');
        expect(response.status()).toBe(405);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Method "PUT" not allowed.'
        });
    });

    test('DELETE should return 405 - Method Not Allowed', async ({ request }) => {

        // try to delete a Model
        const response = await request.delete(`${API_URL}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        
        // check if the response is correct - 405 Method Not Allowed
        expect(response.statusText()).toBe('Method Not Allowed');
        expect(response.status()).toBe(405);

        // check if the error details are correct
        expect(await response.json()).toEqual(
        { 
            detail: 'Method "DELETE" not allowed.'
        });
    });
});

test.describe('API - Pagination Checks', () => {

    test('GET with pagination - offset window has no overlap with first page', async ({ request }) => {

        const NUM_REQUESTS = 10;
        const PAGE_SIZE = 5;

        // submit few valid files
        let public_ids = [];
        for (let i = 0; i < NUM_REQUESTS; i++) {
            const response = await request.post(`${API_BASE_URL}/v1/validationrequest/`, {
                headers: createAuthHeader(TEST_CREDENTIALS),
                multipart: createFormData('fixtures/valid_file.ifc', `valid_file_${NUM_REQUESTS}.ifc`)
            });
            const json_body = await response.json();
            const public_id = json_body['public_id'];
            public_ids.push(public_id);
        }
        public_ids = public_ids.join(',');

        // retrieve first page
        const first = await request.get(`${API_BASE_URL}/validationrequest/?public_ids=${public_ids}&offset=0&limit=${PAGE_SIZE}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        const page1 = await first.json();
        const total = page1.metadata.result_set.total;
      
        // retrieve second page
        const second = await request.get(`${API_BASE_URL}/validationrequest/?public_ids=${public_ids}&offset=${PAGE_SIZE}&limit=${PAGE_SIZE}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });
        const page2 = await second.json();
      
        const page1Ids = new Set(page1.results.map(r => r.public_id));
        const overlap = page2.results.filter(r => page1Ids.has(r.public_id));

        expect(overlap.length).toBe(0);      
        expect(page1.results.length).toBeLessThanOrEqual(PAGE_SIZE);
        expect(page2.results.length).toBeLessThanOrEqual(PAGE_SIZE);
    });

    [ { limit: 5 }, { limit: 10 }, { limit: 15 } ].forEach(({ limit }) => {

        test(`GET with limit ${limit} returns max. ${limit} results`, async ({ request }) => {

            // retrieve limited list
            const res = await request.get(`${API_BASE_URL}/validationrequest/?limit=${limit}`, {
                headers: createAuthHeader(TEST_CREDENTIALS)
            });
            const data = await res.json();

            expect(Array.isArray(data.results)).toBe(true);
            expect(data.results.length).toBeLessThanOrEqual(limit);
            expect(data.metadata.result_set.limit).toBe(limit);
        }); 

    });
});

test.describe('API - Versioning Checks', () => {

    const resources = [ 'validationrequest', 'validationtask', 'validationoutcome', 'model', 'schema', 'swagger-ui', 'redoc' ];

    for (const resource of resources) {
        test(`GET using /api/${resource} returns 200 - OK`, async ({ request }) => {

            // example API query
            const response = await request.get(`${API_HOST_URL}/api/${resource}`, {
                headers: createAuthHeader(TEST_CREDENTIALS)
            });
            
            // check if the response is correct - 200 OK
            expect(response.statusText()).toBe('OK');
            expect(response.status()).toBe(200);
        });
    };

    for (const resource of resources) {
        test(`GET using /api/${resource} and no redirects returns 301 - Moved Permanently`, async ({ request }) => {

            // example API query
            const response = await request.get(`${API_HOST_URL}/api/${resource}`, {
                maxRedirects: 0,
                headers: createAuthHeader(TEST_CREDENTIALS)
            });
            
            // check if the response is correct - 301 Moved Permanently
            expect(response.status()).toBe(301);
            expect(response.statusText()).toBe('Moved Permanently');
            expect(response.headers()['location']).toBe(`/api/v1/${resource}`);
        });
    };
    
    for (const resource of resources) {
        test(`GET using /api/${resource} and no redirects to /api/v1/${resource}`, async ({ request }) => {

            // example API query
            const response = await request.get(`${API_HOST_URL}/api/${resource}`, {
                maxRedirects: 0,
                headers: createAuthHeader(TEST_CREDENTIALS)
            });
            
            // check if the response is correct - 301 Moved Permanently
            expect(response.status()).toBe(301);
            expect(response.statusText()).toBe('Moved Permanently');
            expect(response.headers()['location']).toBe(`/api/v1/${resource}`);
        });
    };

    for (const resource of resources) {
        test(`GET using /api/v1/${resource} returns 200 - OK`, async ({ request }) => {

            // example API query
            const response = await request.get(`${API_HOST_URL}/api/v1/${resource}`, {
                headers: createAuthHeader(TEST_CREDENTIALS)
            });
            
            // check if the response is correct - 200 OK
            expect(response.statusText()).toBe('OK');
            expect(response.status()).toBe(200);
        });
    };

    for (const resource of resources) {
        test(`GET using /api/v1/${resource} returns 404 - NOT FOUND`, async ({ request }) => {

            // example API query
            const response = await request.get(`${API_HOST_URL}/api/v2/${resource}`, {
                headers: createAuthHeader(TEST_CREDENTIALS)
            });
            
            // check if the response is correct - 404 Not Found
            expect(response.statusText()).toBe('Not Found');
            expect(response.status()).toBe(404);
        });
    };

    for (const resource of resources) {
        test(`GET using /api/v123/${resource} returns 404 - NOT FOUND`, async ({ request }) => {

            // example API query
            const response = await request.get(`${API_HOST_URL}/api/v123/${resource}`, {
                headers: createAuthHeader(TEST_CREDENTIALS)
            });
            
            // check if the response is correct - 404 Not Found
            expect(response.statusText()).toBe('Not Found');
            expect(response.status()).toBe(404);
        });
    };
    
    test(`POST using /api/validationrequest and no redirects returns 301 - Moved Permanently`, async ({ request }) => {

        // try to post a valid file to non-versioned endpoint
        const response = await request.post(`${API_BASE_URL}/validationrequest`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc'),
            maxRedirects: 0 // do not follow redirects (as it will result in 301 POST followed by a GET instead of a POST)
        });
        
        // check if the response is correct - 301 Moved Permanently
        expect(response.status()).toBe(301);
        expect(response.statusText()).toBe('Moved Permanently');
        expect(response.headers()['location']).toBe('/api/v1/validationrequest');
    });
});

test.describe('API - Browsers vs Clients', () => {

    test('Browsers will be redirected to /api/swagger-ui', async ({ request }) => {

        // root of /api
        const response = await request.get(`${API_BASE_URL}/`, {
            headers: {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
            },
            maxRedirects: 0
        });

        // check if the response is correct - 302 Found
        expect(response.statusText()).toBe('Found');
        expect(response.status()).toBe(302);
        expect(response.headers()['location']).toBe('/api/swagger-ui/');
    });

    test('Browsers are ultimately redirected to /api/v1/swagger-ui', async ({ request }) => {

        // root of /api
        const response = await request.get(`${API_BASE_URL}/`, {
            headers: {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
            },
            maxRedirects: 5
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);
        expect(response.url()).toBe(`${API_BASE_URL}/v1/swagger-ui/`);
    });

    test('API clients will be redirected to /api/schema', async ({ request }) => {

        // root of /api
        const response = await request.get(`${API_BASE_URL}/`, {
            maxRedirects: 0
        });

        // check if the response is correct - 302 Found
        expect(response.statusText()).toBe('Found');
        expect(response.status()).toBe(302);
        expect(response.headers()['location']).toBe('/api/schema/');
    });

    test('API clients are ultimately redirected to /api/v1/schema', async ({ request }) => {

        // root of /api
        const response = await request.get(`${API_BASE_URL}/`, {
            maxRedirects: 5
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);
        expect(response.url()).toBe(`${API_BASE_URL}/v1/schema/`);
    });  

});

test.describe('API - Documentation', () => {

    test('Swagger-UI should render correctly', async ({ request }) => {

        // navigate to Swagger-UI
        const response = await request.get(`${API_BASE_URL}/v1/swagger-ui`, {
            maxRedirects: 5
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);
    });

    test('Redocly should render correctly', async ({ request }) => {

        // navigate to Redocly
        const response = await request.get(`${API_BASE_URL}/v1/redoc`, {
            maxRedirects: 5
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);
    });

    test('Schema should download correctly', async ({ request }) => {

        // download schema
        const response = await request.get(`${API_BASE_URL}/v1/schema`, {
            maxRedirects: 5
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);
        expect(response.headers()['content-type'] ).toBe('application/vnd.oai.openapi; charset=utf-8');
    });

});