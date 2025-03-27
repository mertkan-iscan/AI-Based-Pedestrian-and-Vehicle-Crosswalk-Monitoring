import torch
import torch.nn as nn


class DeepSortFeatureExtractor(nn.Module):
    def __init__(self, feature_dim=128):
        """
        Initializes a custom Deep SORT feature extraction network.

        Args:
            feature_dim (int): The dimension of the output feature vector.
        """
        super(DeepSortFeatureExtractor, self).__init__()

        # First convolutional block: reduces spatial dimensions by half.
        self.conv1 = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, stride=1, padding=1),  # From 3 to 32 channels.
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )

        # Second convolutional block: further feature extraction and spatial reduction.
        self.conv2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),  # 32 to 64 channels.
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )

        # Third convolutional block.
        self.conv3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1),  # 64 to 128 channels.
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )

        # Fourth block with adaptive average pooling to get a fixed spatial size.
        self.conv4 = nn.Sequential(
            nn.Conv2d(128, 256, kernel_size=3, stride=1, padding=1),  # 128 to 256 channels.
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1))  # Output shape will be (batch_size, 256, 1, 1).
        )

        # Fully connected layer to map the 256 features to the desired feature dimension.
        self.fc = nn.Linear(256, feature_dim)

    def forward(self, x):
        """
        Forward pass of the feature extractor.

        Args:
            x (torch.Tensor): Input tensor with shape (batch_size, 3, H, W)

        Returns:
            torch.Tensor: L2-normalized feature vector with shape (batch_size, feature_dim)
        """
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)
        x = nn.functional.normalize(x, p=2, dim=1)
        return x


if __name__ == '__main__':
    model = DeepSortFeatureExtractor(feature_dim=128)
    model.eval()

    dummy_input = torch.randn(1, 3, 224, 224)

    with torch.no_grad():
        features = model(dummy_input)

    print("Feature vector shape:", features.shape)
