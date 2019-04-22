import logging, sys, json
import torch
from network import freeze_layers, get_pretrained_network, load_checkpoint, predict
from utils import get_predict_input_args


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    logging.info('Starting...')
    input_args = get_predict_input_args()

    image_path = input_args.image_path
    checkpoint_file = '/checkpoint.pth'
    checkpoint_path = input_args.checkpoint + checkpoint_file
    top_k = input_args.top_k
    show_p = input_args.show_probs
    number_of_classes = input_args.number_of_classes
    category_names_path = input_args.category_names

    with open(category_names_path, 'r') as f:
        category_names = json.load(f)

    device = 'cpu'
    if input_args.gpu and torch.cuda.is_available:
        device = 'cuda'

    model, class_from_index, arch = load_checkpoint(checkpoint_path, device, number_of_classes)
    model = freeze_layers(model, arch)
    predict(image_path, model, device, category_names, class_from_index,  top_k, show_probs = show_p)


if __name__ == "__main__":
    main()
