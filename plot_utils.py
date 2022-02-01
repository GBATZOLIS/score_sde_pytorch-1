import torch
import io
import torchvision.transforms as transforms
import PIL
import numpy as np
import copy
from matplotlib import pyplot as plt
from vector_fields.vector_utils import curl, curl_backprop

def generate_grid():
    d=2
    n=500
    c=[0,0]
    x = np.linspace(-d + c[0], d + c[0], n)
    y = np.linspace(-d + c[1], d + c[1], n)
    # Meshgrid
    X,Y = np.meshgrid(x,y)
    return X, Y

def extract_vector_field(score_model, X, Y, t=0.):
    n = len(X[0])
    XYpairs = np.stack([ X.reshape(-1), Y.reshape(-1) ], axis=1)
    xs = torch.tensor(XYpairs, dtype=torch.float, requires_grad=True)
    ts = torch.tensor([t] * n**2, dtype=torch.float)
    out = score_model(xs, ts).view(n,n,-1)
    out_X = out[:,:,0].cpu().detach().numpy()
    out_Y = out[:,:,1].cpu().detach().numpy()
    return out_X, out_Y

def plot_streamlines(model, title='Stream plot', t=0.):
    X,Y = generate_grid()
    out_X, out_Y = extract_vector_field(model, X, Y, t)
    plt.figure(figsize=(10, 10))
    plt.streamplot(X,Y,out_X,out_Y, density=1)
    plt.grid()
    plt.title(title)
    buf = io.BytesIO()
    plt.savefig(buf, format='jpeg')
    buf.seek(0)
    image = PIL.Image.open(buf)
    image = transforms.ToTensor()(image)
    plt.close()
    return image


def plot_curl(model, title='Curl'):
    X,Y = generate_grid()
    out_X, out_Y = extract_vector_field(model, X, Y)
    n = len(X[0])
    dx = 2*2/n
    Z=curl(out_X,out_Y,dx)
    plt.figure(figsize=(10, 10))
    plt.contourf(X, Y, np.abs(Z))
    plt.colorbar()
    plt.xlabel('x')
    plt.ylabel('y')
    plt.gca().set_aspect('equal')
    plt.title(title)
    buf = io.BytesIO()
    plt.savefig(buf, format='jpeg')
    buf.seek(0)
    image = PIL.Image.open(buf)
    image = transforms.ToTensor()(image)
    plt.close()
    return image

def plot_curl_backprop(score_fn, title='Curl', t=0.):
    #model = copy.deepcopy(model).to('cpu')
    #model = model.eval()
    X,Y = generate_grid()
    n = len(X[0])
    XYpairs = np.stack([ X.reshape(-1), Y.reshape(-1) ], axis=1)
    xs = torch.tensor(XYpairs, dtype=torch.float, requires_grad=True, device='cpu')
    ts = torch.tensor([t] * n**2, dtype=torch.float, device='cpu')
    Z=curl_backprop(score_fn,xs, ts).cpu().detach().numpy().reshape(n,n)
    plt.figure(figsize=(10, 10))
    plt.contourf(X, Y, np.abs(Z))
    plt.colorbar()
    plt.xlabel('x')
    plt.ylabel('y')
    plt.gca().set_aspect('equal')
    plt.title(title)
    buf = io.BytesIO()
    plt.savefig(buf, format='jpeg')
    buf.seek(0)
    image = PIL.Image.open(buf)
    image = transforms.ToTensor()(image)
    plt.close()
    return image