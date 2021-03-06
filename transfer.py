import torch
import torch.optim as optim

from torch.autograd import Variable
from torchvision import datasets, transforms
from PIL import Image

from style_network import *
from loss_network import *
from dataset import get_loader
from opticalflow import opticalflow


class Transfer:
    def __init__(self, epoch, data_path, style_path, vgg_path, lr, spatial_a, spatial_b, spatial_r, temporal_lambda, gpu=False, img_shape=(640, 360)):
        self.epoch = epoch
        self.data_path = data_path
        self.style_path = style_path
        self.lr = lr
        self.gpu = gpu

        self.s_a = spatial_a
        self.s_b = spatial_b
        self.s_r = spatial_r 
        self.t_l = temporal_lambda

        self.style_net = StyleNet()
        self.loss_net = LossNet(vgg_path)
        self.style_layer = ['conv1_2', 'conv2_2', 'conv3_2', 'conv4_2']

        self.transform = transforms.Compose([transforms.ToTensor(),
                                             transforms.Normalize((0.485, 0.456, 0.406),
                                                                  (0.229, 0.224, 0.225))])
        self.img_shape = img_shape                                                                  

    def load_style(self):
        transform = trnasforms.Compose([transforms.ToTensor()])

        img = Image.open(self.style_path)
        img = img.resize(self.img_shape)
        img = transform(img).float()
        img = Variable(img, requires_grad=True)
        return img

    def train(self):        
        style_img = self.load_style()

        if self.gpu:
            self.style_net = self.style_net.gpu()
            self.loss_net = self.loss_net.gpu()
            style_img = style_img.gpu()

        adam = optim.Adam(self.style_net.parameters(), lr=self.lr)
        
        loader = get_loader(1, self.data_path, self.img_shape, self.transform)
        print('Data Load Success!!')

        print('Training Start!!')
        for count in range(self.epoch):
            for step, frames in enumerate(loader):
                for i in range(1, len(frames)):
                    x_t = frames[i]
                    x_t1 = frames[i-1]

                    h_xt = self.style_net(x_t)
                    h_xt1 = self.style_net(x_t1)

                    s_xt = self.loss_net(x_t, self.style_layer)
                    s_xt1 = self.loss_net(x_t1, self.style_layer)
                    s_hxt = self.loss_net(h_xt, self.style_layer)
                    s_hxt1 = self.loss_net(h_xt1, self.style_layer)
                    s = self.loss_net(style, self.style_layer)

                    # ContentLoss, conv4_2
                    content_t = ContentLoss(self.gpu)(s_xt[3], s_hxt[3])
                    content_t1 = ContentLoss(self.gpu)(s_xt1[3], s_hxt1[3])
                    content_loss = content_t + content_t1

                    # StyleLoss
                    style_t = None
                    style_t1 = None
                    tv_loss = None
                    for layer in range(len(self.style_layer))
                        style_t += StyleLoss(self.gpu)(s, s_hxt[layer])
                        style_t1 += StyleLoss(self.gpu)(s, s_hxt1[layer])

                        # TVLoss
                        tv_loss = TVLoss(s_hxt[layer])
                    style_loss = style_t + style_t1

                    # Optical flow
                    flow, mask = opticalflow(h_xt.data.numpy(), h_xt1.data.numpy())

                    # Temporal Loss
                    temporal_loss = TemporalLoss(self.gpu)(h_xt, flow, mask)
                    # Spatial Loss
                    spatial_loss = self.s_a * content_loss + self.s_b * style_loss + self.s_r * tv_loss
                    
                    Loss = spatial_loss + self.t_l * temporal_loss
                    Loss.backward(retain_graph=True)
                    adam.step()