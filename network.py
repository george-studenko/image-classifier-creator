from torch import nn, optim
from torchvision import models
import logging
from utils import *
import numpy as np
from PIL import Image

def get_pretrained_network(arch):    
    if arch == 'densenet':
        model = models.densenet161(pretrained=True)
        in_features = model.classifier.in_features

    # elif network == 'vgg':
    #    model = models.vgg19(pretrained=True)
    #    in_features = model.classifier[6].in_features

    elif arch == 'resnet':
        model = models.resnet50(pretrained=True)
        in_features = model.fc.in_features
    else:
        model = models.densenet161(pretrained=True)
        in_features = model.classifier.in_features
        logging.info('Model not found using densenet as default pretrained network')
    return model, in_features


def create_classifier(hidden_units, in_features, number_of_classes):
    classifier = nn.Sequential(        
        nn.Linear(in_features,hidden_units),
        nn.Dropout(),    
        nn.ReLU(),        
        nn.Linear(hidden_units,256),
        nn.ReLU(),         
        nn.Linear(256,128),
        nn.ReLU(),        
        nn.Linear(128,number_of_classes),
        nn.LogSoftmax(dim = 1))  
    classifier.requires_grad=True
    logging.info('Classifier created')
    return classifier


def set_classifier(model,classifier, device, arch):
    # model.classifier = classifier
    if arch == 'densenet':
        model.classifier = classifier
    # elif arch == 'vgg':
    #    model.classifier = classifier
    elif arch == 'resenet':
        model.fc = classifier    
    model.to(device)
    return model

    
def get_optimizer(arch, model, l_rate):
    if arch == 'densenet':
        optimizer = optim.Adam(model.classifier.parameters(), lr = l_rate) 
    elif arch == 'resnet':
        optimizer = optim.Adam(model.fc.parameters(), lr = l_rate)      
    # elif arch =='vgg':
    #    optimizer = optim.Adam(model.classifier[1].parameters(), lr = l_rate)      
    return optimizer


def freeze_layers(model, arch):
    if arch == 'densenet':
        for param in model.parameters():
            param.requires_grad = False
    return model


def validation(model, testloader,criterion,device):
    test_loss = 0
    accuracy = 0
    model.eval()
    
    for images, labels in testloader:
        images, labels = images.to(device), labels.to(device)       
        
        output = model.forward(images)
        test_loss += criterion(output, labels).item()
        
        ps = torch.exp(output)
                   
        # Each probability consist in an array of probabilities, the predicted class is the
        # highest probability of each one, so we need to get the max of the probabilities for each
        # prediction in order to find the predicted_class         
        
        predicted_classes = ps.max(dim=1)[1]
        
        # To find the correct classified items we compare labels with the predicted_classes
        # and we will get back an array of booleans with 1 if the prediction was correct or
        # 0 otherwise
                
        correct_predictions = (labels.data == predicted_classes)
        accuracy += correct_predictions.type(torch.FloatTensor).mean()
        
    return test_loss, accuracy


def save_checkpoint(checkpoint_path, model, class_from_index, hidden_units,
                    learning_rate, batch_size, testing_batch_size, arch):
    checkpoint = {'class_from_index': class_from_index,
                  'hidden_units': hidden_units,
                  'learning_rate': learning_rate,
                  'batch_size': batch_size,
                  'testing_batch_size': testing_batch_size,
                  'arch': arch,
                  'state_dict': model.state_dict()}
    torch.save(checkpoint, checkpoint_path)
    logging.info('Checkpoint saved')


def train_network(model, dataloaders, epochs, device, optimizer, arch):
    # Train Network
    logging.info('Starting training...')
    print_every = 5
    step = 0
    model = model.to(device)
    training_dataloader, validation_dataloader = dataloaders['training'],  dataloaders['validation']
    len_validation_data = len(validation_dataloader)

    if arch == 'densenet':
        criterion = nn.NLLLoss()
    else:
        criterion = nn.CrossEntropyLoss()

    # with active_session():
    for epoch in range(epochs):
        logging.debug('Epoch: {}'.format(epoch))
        running_loss = 0    
        model.train()

        for inputs, y in training_dataloader:
            step += 1
            logging.debug('Step: {}'.format(step))
            optimizer.zero_grad()
            inputs, y = inputs.to(device), y.to(device)

            y_hat = model.forward(inputs)
            loss = criterion(y_hat, y)
            loss.backward()

            optimizer.step()

            running_loss += loss.item()

            if step % print_every == 0:
                model.eval()

                with torch.no_grad():
                    test_loss, accuracy = validation(model, validation_dataloader, criterion, device)

                print("Epoch: {}/{}... ".format(epoch+1, epochs),
                      "Loss: {:.3f}".format(running_loss/print_every),
                      "Test Loss: {:.3f}".format(test_loss / len_validation_data),
                      "Test Accuracy: {:.3f}".format(accuracy / len_validation_data))

                running_loss = 0
                model.train()    
    return model


def load_checkpoint(checkpoint_path, device, number_of_classes):
    # Load checkpoint
    checkpoint = torch.load(checkpoint_path)
    arch = checkpoint['arch']
    hidden_units = checkpoint['hidden_units']

    # Rebuild Model
    model, in_features = get_pretrained_network(arch)
    classifier = create_classifier(hidden_units, in_features, number_of_classes)
    model = set_classifier(model, classifier, device, arch)

    model.load_state_dict(checkpoint['state_dict'])
    class_from_index = checkpoint['class_from_index']
    logging.info('Checkpoint Loaded')
    return model, class_from_index, arch


def process_image(image):
    ''' Scales, crops, and normalizes a PIL image for a PyTorch model,
        returns an Numpy array
    '''
    img = Image.open(image)

    transformations = transforms.Compose([transforms.Resize(256),
                                          transforms.CenterCrop(224),
                                          transforms.ToTensor(),
                                          transforms.Normalize(means, std)])
    img = transformations(img)

    np_image = np.array(img)

    return np_image


def predict(image_path, model, device, cat_to_name, class_from_index,  topk=5, show_probs = False):
    ''' Predict the class (or classes) of an image using a trained deep learning model.
    '''
    image = process_image(image_path)
    image = torch.from_numpy(image)
    image = image.to(device)

    model.eval()

    image.unsqueeze_(0)

    output = model.forward(image)

    ps = torch.exp(output)

    probs, classes = ps.topk(topk)
    probs, classes = probs.cpu().detach().numpy(), classes.cpu().detach().numpy()

    # Create labels with category names for the topK predictions
    categories = [cat_to_name[class_from_index[idx]] for idx in classes[0]]
    print(sum(probs))
    predictions = zip(categories, probs.T)

    if show_probs:
        print()
        print('##############################')
        print()
        print('  TOP {} probabilities are:'.format(topk))
        print()

        for cat, pred in predictions:
            print('  {}: {}%'.format(cat, round(pred.item(),2) * 100))
        print()
        if 'predict_img' in image_path:
            # Get true label
            true_idx = image_path.split('/')[1]
            # cat_to_name[class_from_index]
            true_label = cat_to_name[true_idx]
            print('  True label: {}'.format(true_label))
            print()
        print('##############################')
        print()
    else:
        print()
        print('##############################')
        print()
        print('  The image is most likely a:')
        print()

        for cat, pred in predictions:
            print('  {}'.format(cat))
            print()
        if 'predict_img' in image_path:
            # Get true label
            true_idx = image_path.split('/')[1]
            # cat_to_name[class_from_index]
            true_label = cat_to_name[true_idx]
            print('  True label: {}'.format(true_label))
            print()
        print('##############################')
        print()
