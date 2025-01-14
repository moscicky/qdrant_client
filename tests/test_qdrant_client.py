import os
import random
import uuid
from pprint import pprint
from tempfile import mkdtemp
from time import sleep

import numpy as np

from qdrant_client import QdrantClient
from qdrant_openapi_client.models.models import Filter, FieldCondition, Range, PointOperationsAnyOf, \
    PointInsertOperationsAnyOf1, PointStruct, PointRequest, PayloadOpsAnyOf, PayloadOpsAnyOfSetPayload, \
    PointOperationsAnyOf1, PointOperationsAnyOf1DeletePoints

DIM = 100
NUM_VECTORS = 1_000
COLLECTION_NAME = 'client_test'


def random_payload():
    for i in range(NUM_VECTORS):
        yield {
            "id": i + 100,
            "text_data": uuid.uuid4().hex,
            "rand_number": random.random(),
            "text_array": [uuid.uuid4().hex, uuid.uuid4().hex]
        }


def create_random_vectors():
    vectors_path = os.path.join(mkdtemp(), 'vectors.npy')
    fp = np.memmap(vectors_path, dtype='float32', mode='w+', shape=(NUM_VECTORS, DIM))

    data = np.random.rand(NUM_VECTORS, DIM).astype(np.float32)
    fp[:] = data[:]
    fp.flush()
    return vectors_path


def test_qdrant_client_integration():
    vectors_path = create_random_vectors()
    vectors = np.memmap(vectors_path, dtype='float32', mode='r', shape=(NUM_VECTORS, DIM))
    payload = random_payload()

    client = QdrantClient()

    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vector_size=DIM
    )

    # Call Qdrant API to retrieve list of existing collections
    collections = client.http.collections_api.get_collections().result.collections

    # Prfrom qdrant_client import QdrantClientint all existing collections
    for collection in collections:
        print(collection.dict())

    # Retrieve detailed information about newly created collection
    test_collection = client.http.collections_api.get_collection(COLLECTION_NAME)
    pprint(test_collection.dict())

    # Upload data to a new collection
    client.upload_collection(
        collection_name=COLLECTION_NAME,
        vectors=vectors,
        payload=payload,
        ids=None,  # Let client auto-assign sequential ids
        parallel=2
    )

    # By default, Qdrant indexes data updates asynchronously, so client don't need to wait before sending next batch
    # Let's give it a second to actually add all points to a collection.
    # If want need to change this behaviour - simply enable synchronous processing by enabling `wait=true`
    sleep(1)

    # Create payload index for field `random_num`
    # If indexed field appear in filtering condition - search operation could be performed faster
    index_create_result = client.create_payload_index(COLLECTION_NAME, "random_num")
    pprint(index_create_result.dict())

    # Let's now check details about our new collection
    test_collection = client.http.collections_api.get_collection(COLLECTION_NAME)
    pprint(test_collection.dict())

    # Now we can actually search in the collection
    # Let's create some random vector
    query_vector = np.random.rand(DIM)

    #  and use it as a query
    hits = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=None,  # Don't use any filters for now, search across all indexed points
        append_payload=True,  # Also return a stored payload for found points
        top=5  # Return 5 closest points
    )

    # Print found results
    print("Search result:")
    for hit in hits:
        print(hit)

    # Let's now query same vector with filter condition
    hits = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=Filter(
            must=[  # These conditions are required for search results
                FieldCondition(
                    key='rand_number',  # Condition based on values of `rand_number` field.
                    range=Range(
                        gte=0.5  # Select only those results where `rand_number` >= 0.5
                    )
                )
            ]
        ),
        append_payload=True,  # Also return a stored payload for found points
        top=5  # Return 5 closest points
    )

    print("Filtered search result (`random_num` >= 0.5):")
    for hit in hits:
        print(hit)


def test_points_crud():

    client = QdrantClient()

    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vector_size=DIM
    )

    # Create a single point

    client.http.points_api.update_points(
        name=COLLECTION_NAME,
        wait=True,
        collection_update_operations=PointOperationsAnyOf(
            upsert_points=PointInsertOperationsAnyOf1(
                points=[
                    PointStruct(
                        id=123,
                        payload={"test": "value"},
                        vector=np.random.rand(DIM).tolist()
                    )
                ]
            )
        )
    )

    # Read a single point

    points = client.http.points_api.get_points(COLLECTION_NAME, point_request=PointRequest(ids=[123]))

    print("read a single point", points)

    # Update a single point

    client.http.points_api.update_points(
        name=COLLECTION_NAME,
        collection_update_operations=PayloadOpsAnyOf(
            set_payload=PayloadOpsAnyOfSetPayload(
                payload={
                    "test2": ["value2", "value3"]
                },
                points=[123]
            )
        )
    )

    # Delete a single point

    client.http.points_api.update_points(
        name=COLLECTION_NAME,
        collection_update_operations=PointOperationsAnyOf1(
            delete_points=PointOperationsAnyOf1DeletePoints(ids=[123])
        )
    )


if __name__ == '__main__':
    test_qdrant_client_integration()
    test_points_crud()
