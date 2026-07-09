import os
import json

# Match your exact multi-level folder paths
RUNS_DIR = os.path.join('data', 'outputs', 'runs')
DATASETS_DIR = os.path.join('data', 'datasets')
OUTPUT_FILE = 'data.js'

benchmark_data = {
    "prompts": {
        "variant1": "System instructions used for Variant 1 setup...",
        "variant2": "System instructions used for Variant 2 setup...",
        "variant3": "System instructions used for Variant 3 setup...",
        "variant4": "System instructions used for Variant 4 setup..."
    },
    "datasets": {}
}

grouped_charts = {}

print("====================================================")
print(f"1. Scanning image assets folder: '{DATASETS_DIR}'...")
print("====================================================")

# 1. Map all chart images inside your dataset folders (handles nested paths and different extensions)
image_mapping = {}
if os.path.exists(DATASETS_DIR):
    for root, dirs, files in os.walk(DATASETS_DIR):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.svg')):
                name_without_ext = os.path.splitext(file)[0]
                rel_path = os.path.relpath(os.path.join(root, file), '.').replace('\\', '/')
                # Store by exact file name base
                image_mapping[name_without_ext] = rel_path
    print(f"Indexed {len(image_mapping)} image files successfully.")
else:
    print(f"Warning: Directory '{DATASETS_DIR}' not found.")

print("\n====================================================")
print(f"2. Deep scanning subfolders inside: '{RUNS_DIR}'...")
print("====================================================")

# 2. Recursively crawl down into every chart subfolder under data/outputs/runs
json_count = 0

if not os.path.exists(RUNS_DIR):
    print(f"Error: Path '{RUNS_DIR}' not found. Verify you are running this from your project root folder!")
else:
    for root, dirs, files in os.walk(RUNS_DIR):
        for filename in files:
            if filename.endswith('.json'):
                json_count += 1
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        run_data = json.load(f)
                    
                    dataset = run_data.get('dataset_source', 'unassigned_dataset')
                    chart_id = run_data.get('chart_id', 'unassigned_chart')
                    
                    if dataset not in grouped_charts:
                        grouped_charts[dataset] = {}
                        
                    # Normalize format structures across different model outputs
                    parsed = run_data.get('parsed_output', {})
                    if not parsed or not isinstance(parsed, dict):
                        parsed = run_data
                    
                    if chart_id not in grouped_charts[dataset]:
                        flags = run_data.get('flags', {})
                        if not isinstance(flags, dict):
                            flags = parsed.get('flags', {})
                        
                        direct_claims = flags.get('direct_claims', []) if isinstance(flags, dict) else []
                        fallback_title = direct_claims[0] if direct_claims else chart_id
                        
                        # --- Smart Fuzzy Image Resolution Line ---
                        # Handles cases where filename drops the prefix (e.g. 'hci_6adc...' vs '6adc...')
                        clean_id = chart_id
                        for prefix in ['hci_', 'olli_', 'vistext_', 'owid_']:
                            if clean_id.startswith(prefix):
                                clean_id = clean_id[len(prefix):]
                        
                        resolved_image = f"data/datasets/{dataset}/images/{chart_id}.jpg" # baseline fallback
                        if chart_id in image_mapping:
                            resolved_image = image_mapping[chart_id]
                        elif clean_id in image_mapping:
                            resolved_image = image_mapping[clean_id]
                        else:
                            # Substring fallback search check
                            for img_base, img_path in image_mapping.items():
                                if img_base in chart_id or clean_id in img_base:
                                    resolved_image = img_path
                                    break
                        
                        grouped_charts[dataset][chart_id] = {
                            "id": chart_id,
                            "title": fallback_title,
                            "image": resolved_image,
                            "outputs": []
                        }
                    
                    # Core quantitative metrics normalized extractor
                    ident = parsed.get('identification', {}) if isinstance(parsed, dict) else {}
                    meta_comp = ident.get('metadata_completeness', {}) if isinstance(ident, dict) else {}
                    
                    def normalize_score(field_key):
                        field_val = meta_comp.get(field_key, 0)
                        if isinstance(field_val, dict):
                            return field_val.get('score', 0)
                        return field_val

                    output_entry = {
                        "model_id": run_data.get('model_id', 'Unknown Model'),
                        "variant": int(run_data.get('variant', 1)),
                        "enabled_features": run_data.get('enabled_features', []),
                        "metadata_completeness": {
                            "data_values": normalize_score('data_values'),
                            "trend_magnitude": normalize_score('trend_magnitude'),
                            "chart_subject_domain": normalize_score('chart_subject_domain'),
                            "overall": normalize_score('overall')
                        },
                        "generated_description": parsed.get('generated_description', {}) if isinstance(parsed, dict) else {}
                    }
                    
                    grouped_charts[dataset][chart_id]["outputs"].append(output_entry)
                    
                except Exception as e:
                    print(f"Skipping corrupt or unparseable run file {filename}: {e}")

    print(f"Successfully located and compiled {json_count} total evaluation runs.")

    # 3. Structure maps back to standard array records for interface tracking
    for dataset_key, charts_dict in grouped_charts.items():
        benchmark_data["datasets"][dataset_key] = list(charts_dict.values())

    # Write out data compilation
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_f:
        out_f.write(f"const BENCHMARK_DATA = {json.dumps(benchmark_data, indent=2)};")

    print(f"\n🎉 Success! All models and variants written completely into '{OUTPUT_FILE}'.")