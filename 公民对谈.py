import os
import requests

def process_text(prompt, text, api_base_url, api_key, model):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    data = {
        'model': model,
        'messages': [
            {'role': 'user', 'content': f"{prompt}\n{text}"}
        ]
    }

    try:
        response = requests.post(f"{api_base_url}/chat/completions", headers=headers, json=data)
        if response.status_code == 200:
            output_text = response.json()['choices'][0]['message']['content'].strip()
            return output_text
        else:
            print(f"请求失败: {response.status_code}, 错误信息: {response.text}")
            return None

    except Exception as e:
        print(f"错误: {e}")
        return None


def read_text_from_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


def write_text_to_file(file_path, text):
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(text)


def save_original_segments(text, split_dir, max_length=512):
    """
    将原始文本按分段切割并保存到 split_dir 文件夹中。
    每个分段存储为单独文件，文件名格式为 segment_{序号}.txt。
    """
    if not os.path.exists(split_dir):
        os.makedirs(split_dir)

    lines = text.splitlines()
    current_chunk = ""
    segment_num = 1

    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_length:
            # 保存当前分段
            file_path = os.path.join(split_dir, f"segment_{segment_num}.txt")
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(current_chunk.strip())
            print(f"原始分段 {segment_num} 已保存到 {file_path}")
            segment_num += 1
            current_chunk = ""

        current_chunk += line.strip() + "\n"

    if current_chunk:
        # 保存最后一个分段
        file_path = os.path.join(split_dir, f"segment_{segment_num}.txt")
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(current_chunk.strip())
        print(f"原始分段 {segment_num} 已保存到 {file_path}")


def process_segments_with_gpt(prompt, split_dir, output_dir, api_base_url, api_key, model, 
                              api_base_url_reserve=None, api_key_reserve=None, model_reserve=None):
    """
    使用分割后的 segment 文件内容逐个进行 GPT 询问，并将结果保存到 output_dir 文件夹中。
    支持备用模型处理逻辑。
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 获取所有分割的文本文件
    segments = sorted([f for f in os.listdir(split_dir) if f.startswith("segment_") and f.endswith(".txt")])

    failed_segments = []  # 用于记录失败的分段

    for segment_file in segments:
        segment_path = os.path.join(split_dir, segment_file)
        output_path = os.path.join(output_dir, segment_file)

        # 跳过已处理的文件
        if os.path.exists(output_path):
            print(f"文件已处理，跳过: {output_path}")
            continue

        # 读取分段内容
        text = read_text_from_file(segment_path)
        print(f"正在处理文件: {segment_path}")

        # 调用主模型进行处理
        processed_text = process_text(prompt, text, api_base_url, api_key, model)

        # 如果主模型失败，尝试使用备用模型
        if not processed_text and api_base_url_reserve and api_key_reserve and model_reserve:
            print(f"主模型处理失败，尝试使用备用模型处理文件: {segment_path}")
            processed_text = process_text(prompt, text, api_base_url_reserve, api_key_reserve, model_reserve)

        if processed_text:
            # 保存处理后的内容
            write_text_to_file(output_path, processed_text)
            print(f"处理完成，已保存到: {output_path}")
        else:
            print(f"备用模型也处理失败，跳过文件: {segment_path}")
            failed_segments.append(segment_file)  # 记录失败分段文件名

    # 如果有失败的分段，将其记录到日志文件
    if failed_segments:
        failed_log_path = os.path.join(output_dir, "failed_segments.log")
        with open(failed_log_path, 'w', encoding='utf-8') as log_file:
            log_file.write("\n".join(failed_segments))
        print(f"以下分段处理失败，已记录到日志文件: {failed_log_path}")

def merge_adjacent_speakers(output_dir, merged_file_path):
    """
    合并处理后的文本中连续相同发言人的内容。
    """
    # 获取所有处理后的文本文件，并根据文件名中的数字部分进行排序
    processed_files = sorted(
        [f for f in os.listdir(output_dir) if f.startswith("segment_") and f.endswith(".txt")],
        key=lambda x: int(x.split('_')[1].split('.')[0])  # 提取数字部分进行排序
    )

    # Step 1: 将所有处理后的文本文件内容合并成一个完整的文本
    merged_content = ""
    for file_name in processed_files:
        file_path = os.path.join(output_dir, file_name)
        content = read_text_from_file(file_path).strip()
        merged_content += content + "\n\n"

    # Step 2: 对合并后的文本进行连续相同发言人的内容合并
    merged_lines = merged_content.splitlines()
    final_content = ""
    last_speaker = None
    current_content = ""

    for line in merged_lines:
        line = line.strip()
        if not line:
            continue

        # 获取当前段落的发言人编号
        if line.startswith("[") and "]" in line:
            current_speaker = line.split("]")[0] + "]"

            # 如果发言人改变或是第一段
            if last_speaker != current_speaker:
                if current_content:
                    final_content += current_content.strip() + "\n\n"
                current_content = line  # 重置当前段落
                last_speaker = current_speaker
            else:
                # 如果发言人相同，合并内，并添加回车生成段落
                # current_content += " " + line[len(current_speaker):].strip()
                current_content += "\n"+ line[len(current_speaker):].strip()
        else:
            # 如果没有发言人编号，直接添加到当前段落
            current_content += " " + line.strip()

    # 添加最后一段
    if current_content:
        final_content += current_content.strip()

    # Step 3: 保存合并后的内容
    # final_content将[0]替换成[安溥]
    final_content = final_content.replace("[0]", "[安溥]")

    with open(merged_file_path, 'w', encoding='utf-8') as merged_file:
        merged_file.write(final_content)
    print(f"合并后的内容已保存到: {merged_file_path}")

def rename_txt_files(folder_path):
    """
    遍历指定文件夹中的所有 .txt 文件，去掉文件名中的“通用语音识别_”和“.mp3”。

    :param folder_path: 文件夹路径
    """
    # 检查文件夹是否存在
    if not os.path.isdir(folder_path):
        print(f"指定的路径 '{folder_path}' 不是一个有效的文件夹。")
        return

    # 遍历文件夹中的所有文件
    for filename in os.listdir(folder_path):
        # 检查文件是否是 .txt 文件
        if filename.endswith('.txt'):
            # 构造新的文件名
            new_filename = filename.replace('通用语音识别_', '').replace('.mp3', '')

            # 获取完整的文件路径
            old_file_path = os.path.join(folder_path, filename)
            new_file_path = os.path.join(folder_path, new_filename)

            # 重命名文件
            os.rename(old_file_path, new_file_path)

            print(f'Renamed: {filename} to {new_filename}')

# 示例调用
# rename_txt_files('你的文件夹路径')

if __name__ == "__main__":
    prompt = """【公民对谈整理指令】
▲核心要求：严格保留原始[角色编号]标识
▲处理规则：
1. 角色标识：完整保留原文中的[0][1][2]等编号前缀
   （示例：[0] 请专家先做说明 → 保留不变）

二、内容处理规则
1. 语音识别修正：
    - 修正同音错别字（例："预赛"→"预算"；"公识"→"共识"；"实事"→"实施"；"工龄对谈"->"公民对谈"）
    - 修复断句错误（例："我认/为应该"→"我认为应该"）
    - 主持人的原名叫安溥，艺名叫张悬。因此有可能出现"张悬"和"安溥"两个名字同音错别字的情况，需要根据上下文进行修正。
2. 口语规范化：
    - 删除冗余词："呃、嗯、那个、然后呢、就是说"
    - 修正重复/矛盾表述（例："我们需不需要要"→"是否需要"）

3. 禁止操作：
    - 不得合并或拆分发言段落
    - 不得添加时间戳/注释/格式符号
    - 不得修改原始观点表述（仅修正表达形式）

4. 专业表述：
    - 保留社会学术语原貌
    - 统一数字格式（例："二十个"→"20个"；"百分之三十"→"30%"）

示例处理：
原文：
[0]那个...我们是不是应该呃，先讨论预算？
[1]其实我觉得这个需不需要要分阶段实施... 

输出：
[0] 我们是不是应该先讨论预算？
[1] 是否需要分阶段实施...
    """
   

    custom_url = ""
    api_key = ""
    model = "deepseek-v3"

    # 配置备用模型 API 信息
    custom_url_reserve = ""
    api_key_reserve = ""  # 备用模型 API 密钥

    model_reserve = "gpt-4o-mini"

    # 输入文件路径
    input_fold = "公民对谈"
    rename_txt_files(input_fold)

    # 处理所有输入txt文件
    input_files = [f for f in os.listdir(input_fold) if f.endswith(".txt")]

    for input_file in input_files:
        input_file_path = os.path.join(input_fold, input_file )
        text = read_text_from_file(input_file_path)

        # Step 1: 保存分割后的原始文本到 split 文件夹
        split_dir = os.path.join("split", os.path.splitext(os.path.basename(input_file_path))[0])
        save_original_segments(text, split_dir)

        # Step 2: 使用分割后的 segment 文件直接进行 GPT 处理
        output_dir = os.path.join("result", os.path.splitext(os.path.basename(input_file_path))[0])
        process_segments_with_gpt(prompt, split_dir, output_dir, 
                                api_base_url=custom_url, api_key=api_key, model=model,
                                api_base_url_reserve=custom_url_reserve, api_key_reserve=api_key_reserve, model_reserve=model_reserve)

        # Step 3: 合并同一发言人的内容
        merged_file_path = os.path.join("result", f"{os.path.splitext(os.path.basename(input_file_path))[0]}_merged.txt")
        merge_adjacent_speakers(output_dir, merged_file_path)

        print(f"所有处理后的文本已保存到目录: {output_dir}")
        print(f"合并后的文本已保存到文件: {merged_file_path}")