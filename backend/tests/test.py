from datasets import Dataset, load_dataset

iterable_ds = load_dataset("deepmind/code_contests", split="train", streaming=True)

print("Downloading")
records = list(iterable_ds.take(300))

mini_ds = Dataset.from_list(records)

mini_ds.to_json("code_contests_100.json")

print("Completed")
