from datasets import Dataset, load_dataset

iterable_ds = load_dataset("deepmind/code_contests", split="train", streaming=True)

print("Downloading")

fields_to_remove = (
    "cf_contest_id",
    "incorrect_solutions",
    "solutions",
    "untranslated_description",
    "",
)

records = []

for i, record in enumerate(iterable_ds):
    if i >= 1000:
        break
    filtered_record = {k: v for k, v in record.items() if k not in fields_to_remove}
    records.append(filtered_record)

mini_ds = Dataset.from_list(records)

mini_ds.to_json("tests.json")

print("Completed")
