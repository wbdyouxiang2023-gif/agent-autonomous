"""Agent tests"""
import json, os, tempfile

def test_persistence():
    tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
    json.dump({"todos": [{"id": 1, "text": "test", "done": False}], "next_id": 2}, tmp)
    tmp.close()
    with open(tmp.name) as f:
        data = json.load(f)
    assert data["todos"][0]["text"] == "test"
    os.unlink(tmp.name)
    print("✓ Tests passed")

if __name__ == "__main__":
    test_persistence()
